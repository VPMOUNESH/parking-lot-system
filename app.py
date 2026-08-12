"""
Flask API server for Parking Lot Management System
"""

from flask import Flask, request, jsonify, session, send_from_directory
import os
import math
import json
from datetime import datetime, timedelta

try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    def CORS(app, **kwargs):
        @app.after_request
        def after_request(response):
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
            return response
        return None

from parking_lot.auth import AuthManager
from parking_lot.lot import ParkingLot
from parking_lot.vehicle import VehicleFactory
from parking_lot.payment import Payment
from parking_lot.enums import PaymentMethod, VehicleType, SpotType, TicketStatus, HOURLY_RATES
from parking_lot.admin import Admin

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)

secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError('SECRET_KEY must be set in production')
    secret_key = 'development-only-secret-key'
app.secret_key = secret_key
CORS(app)

auth_manager = AuthManager()
parking_lot = ParkingLot()
admin_manager = Admin(parking_lot)

# ─────────────────────────────────────────────────────────────────────────────
# FRONTEND ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(BASE_DIR, path)

# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    user_type = data.get('type', 'user')

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    if user_type == 'admin':
        if auth_manager.admin_exists():
            return jsonify({'success': False, 'message': 'Admin already exists'}), 400
        if auth_manager.create_admin(username, password):
            return jsonify({'success': True, 'message': 'Admin registered successfully'}), 201
        else:
            return jsonify({'success': False, 'message': 'Username already taken'}), 400
    else:
        if auth_manager.create_user(username, password):
            return jsonify({'success': True, 'message': 'User registered successfully'}), 201
        else:
            return jsonify({'success': False, 'message': 'Username already taken'}), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    user_type = data.get('type', 'user')

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    if user_type == 'admin':
        if auth_manager.authenticate_admin(username, password):
            session['user_type'] = 'admin'
            session['username'] = username
            return jsonify({'success': True, 'message': 'Login successful', 'user_type': 'admin'}), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    else:
        if auth_manager.authenticate_user(username, password):
            session['user_type'] = 'user'
            session['username'] = username
            return jsonify({'success': True, 'message': 'Login successful', 'user_type': 'user'}), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'}), 200

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    if 'user_type' in session:
        return jsonify({
            'success': True,
            'user_type': session.get('user_type'),
            'username': session.get('username')
        }), 200
    return jsonify({'success': False, 'message': 'Not logged in'}), 401

# ─────────────────────────────────────────────────────────────────────────────
# PARKING LOT INFO ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/lot/info', methods=['GET'])
def get_lot_info():
    return jsonify({
        'lot_id': parking_lot.lot_id,
        'name': parking_lot.name,
        'mobile': parking_lot.mobile,
        'address': parking_lot.address,
        'total_floors': len(parking_lot.floors),
        'total_vehicles': len(parking_lot.vehicle_tickets)
    }), 200

@app.route('/api/lot/floors', methods=['GET'])
def get_floors_status():
    floors_data = []
    for floor_num, floor in parking_lot.floors.items():
        available_by_type = {}
        for spot_type in set(spot.spot_type for spot in floor.spots):
            available = sum(1 for spot in floor.spots 
                          if spot.spot_type == spot_type and spot.is_available)
            total = sum(1 for spot in floor.spots if spot.spot_type == spot_type)
            available_by_type[spot_type.value] = {'available': available, 'total': total}
        
        floors_data.append({
            'floor_number': floor_num,
            'floor_label': 'Ground Floor 1' if floor_num == 1 else f'Floor {floor_num}',
            'total_spots': len(floor.spots),
            'available_spots': sum(1 for spot in floor.spots if spot.is_available),
            'occupied_spots': sum(1 for spot in floor.spots if not spot.is_available),
            'spots_by_type': available_by_type
        })
    
    return jsonify({'floors': floors_data}), 200

# ─────────────────────────────────────────────────────────────────────────────
# VEHICLE ENTRY/EXIT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/vehicle/entry', methods=['POST'])
def vehicle_entry():
    data = request.json
    vehicle_type = data.get('vehicle_type')
    vehicle_number = data.get('vehicle_number', '').strip().upper()
    owner_name = data.get('owner_name', '').strip()
    color = data.get('color', '').strip()

    if not all([vehicle_type, vehicle_number, owner_name]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    try:
        v_type = None
        for vt in VehicleType:
            if vt.value.upper() == vehicle_type.upper() or vt.name.upper() == vehicle_type.upper():
                v_type = vt
                break
        
        if not v_type:
            return jsonify({'success': False, 'message': f'Invalid vehicle type: {vehicle_type}'}), 400
            
        owner_mobile = data.get('owner_mobile', '').strip()

        vehicle = VehicleFactory.create(
            v_type=v_type,
            number=vehicle_number,
            color=color,
            owner=owner_name,
            mobile=owner_mobile
        )
        
        ticket = parking_lot.vehicle_entry(vehicle)
        if ticket:
            return jsonify({
                'success': True,
                'message': 'Vehicle entry successful',
                'ticket': {
                    'ticket_id': ticket.ticket_id,
                    'vehicle_number': vehicle_number,
                    'vehicle_type': vehicle_type,
                    'owner_name': owner_name,
                    'spot_number': ticket.spot.spot_number,
                    'floor_label': ticket.floor_label,
                    'entry_time': ticket.entry_time.isoformat()
                }
            }), 201
        else:
            return jsonify({'success': False, 'message': 'Failed to park vehicle. Lot may be full.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/vehicle/lookup', methods=['POST'])
def lookup_vehicle():
    data = request.json
    vehicle_number = data.get('vehicle_number', '').strip().upper()

    if not vehicle_number:
        return jsonify({'success': False, 'message': 'Vehicle number required'}), 400

    ticket_id = parking_lot.vehicle_tickets.get(vehicle_number)
    if not ticket_id:
        return jsonify({'success': False, 'message': 'Vehicle not found in parking lot'}), 404

    ticket = parking_lot.tickets.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': 'Ticket not found'}), 404

    mins = ticket.duration_minutes()
    hrs = int(mins // 60)
    rem = int(mins % 60)

    return jsonify({
        'success': True,
        'ticket': {
            'ticket_id': ticket.ticket_id,
            'vehicle_number': ticket.vehicle.vehicle_number,
            'vehicle_type': ticket.vehicle.vehicle_type.value,
            'owner_name': ticket.vehicle.owner_name,
            'spot_number': ticket.spot.spot_number,
            'floor_label': ticket.floor_label,
            'entry_time': ticket.entry_time.isoformat(),
            'status': ticket.status.value,
            'duration': f'{hrs}h {rem}m'
        }
    }), 200

@app.route('/api/vehicle/lost-ticket', methods=['POST'])
def report_lost_ticket():
    data = request.json
    vehicle_number = data.get('vehicle_number', '').strip().upper()
    if not vehicle_number:
        return jsonify({'success': False, 'message': 'Vehicle number required'}), 400
    
    ticket_id = parking_lot.vehicle_tickets.get(vehicle_number)
    if not ticket_id:
        return jsonify({'success': False, 'message': 'Vehicle not found in parking lot'}), 404
        
    try:
        parking_lot.report_lost_ticket(vehicle_number)
        return jsonify({'success': True, 'message': f'Ticket for {vehicle_number} has been marked as LOST'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY BOARD ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/display/all', methods=['GET'])
def get_all_displays():
    displays = []
    for floor_num, floor in parking_lot.floors.items():
        floor_label = 'Ground Floor 1' if floor_num == 1 else f'Floor {floor_num}'
        spots_by_type = {}
        for spot_type in set(spot.spot_type for spot in floor.spots):
            available = sum(1 for spot in floor.spots 
                          if spot.spot_type == spot_type and spot.is_available)
            total = sum(1 for spot in floor.spots if spot.spot_type == spot_type)
            spots_by_type[spot_type.value] = {'available': available, 'total': total}
        
        displays.append({
            'floor_number': floor_num,
            'floor_label': floor_label,
            'total_spots': len(floor.spots),
            'available_spots': sum(1 for spot in floor.spots if spot.is_available),
            'occupied_spots': sum(1 for spot in floor.spots if not spot.is_available),
            'spots_by_type': spots_by_type
        })
    
    return jsonify({'success': True, 'displays': displays}), 200

@app.route('/api/display/floor/<int:floor_num>', methods=['GET'])
def get_floor_display(floor_num):
    floor = parking_lot.floors.get(floor_num)
    if not floor:
        return jsonify({'success': False, 'message': f'Floor {floor_num} not found'}), 404
    
    spots_data = []
    for idx, spot in enumerate(floor.spots, 1):
        vehicle_info = None
        if not spot.is_available:
            for ticket in parking_lot.tickets.values():
                if ticket.status == TicketStatus.ACTIVE and ticket.spot.spot_number == spot.spot_number:
                    vehicle_info = {
                        'vehicle_number': ticket.vehicle.vehicle_number,
                        'vehicle_type': ticket.vehicle.vehicle_type.value,
                        'owner_name': ticket.vehicle.owner_name,
                        'color': ticket.vehicle.color,
                        'entry_time': ticket.entry_time.isoformat()
                    }
                    break
        
        spots_data.append({
            'spot_id': spot.spot_id,
            'spot_number': str(idx),
            'spot_type': spot.spot_type.value,
            'is_available': spot.is_available,
            'vehicle_info': vehicle_info
        })
    
    floor_label = 'Ground Floor 1' if floor_num == 1 else f'Floor {floor_num}'
    return jsonify({
        'success': True,
        'floor_number': floor_num,
        'floor_label': floor_label,
        'total_spots': len(floor.spots),
        'available_spots': sum(1 for spot in floor.spots if spot.is_available),
        'spots': spots_data
    }), 200

# ─────────────────────────────────────────────────────────────────────────────
# PAYMENT ENDPOINTS - EXACT CALCULATION
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/payment/calculate', methods=['POST'])
def calculate_payment():
    data = request.json
    vehicle_number = data.get('vehicle_number', '').strip().upper()

    ticket_id = parking_lot.vehicle_tickets.get(vehicle_number)
    if not ticket_id:
        return jsonify({'success': False, 'message': 'Vehicle not found'}), 404

    ticket = parking_lot.tickets.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': 'Ticket not found'}), 404

    if ticket.status.value == 'PAID':
        return jsonify({'success': False, 'message': 'Already paid'}), 400

    mins = ticket.duration_minutes()
    hours = mins / 60
    rate = HOURLY_RATES[ticket.vehicle.vehicle_type]
    amount = round(hours * rate, 2)
    
    if mins < 10:
        amount = round((10/60) * rate, 2)
    
    hrs = int(mins // 60)
    rem = int(mins % 60)

    return jsonify({
        'success': True,
        'payment': {
            'ticket_id': ticket_id,
            'vehicle_number': vehicle_number,
            'amount': amount,
            'hourly_rate': rate,
            'duration_hours': hrs,
            'duration_minutes': rem,
            'total_duration_minutes': int(mins)
        }
    }), 200

@app.route('/api/payment/process', methods=['POST'])
def process_payment():
    data = request.json
    vehicle_number = data.get('vehicle_number', '').strip().upper()
    payment_method = data.get('payment_method', 'Cash')

    ticket_id = parking_lot.vehicle_tickets.get(vehicle_number)
    if not ticket_id:
        return jsonify({'success': False, 'message': 'Vehicle not found'}), 404

    ticket = parking_lot.tickets.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': 'Ticket not found'}), 404

    if ticket.status.value == 'PAID':
        return jsonify({'success': False, 'message': 'Already paid'}), 400

    try:
        method = PaymentMethod[payment_method.upper().replace(' ', '_')]
        result = parking_lot.vehicle_exit(vehicle_number, method)
        
        if result:
            payment = result
            return jsonify({
                'success': True,
                'message': 'Payment processed successfully',
                'receipt': {
                    'payment_id': payment.payment_id,
                    'ticket_id': ticket_id,
                    'vehicle_number': vehicle_number,
                    'amount': payment.amount,
                    'method': payment.method.value,
                    'status': payment.status.value
                }
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Payment processing failed'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# ─────────────────────────────────────────────────────────────────────────────
# PARKING CHARGES LIST ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/charges', methods=['GET'])
def get_charges_list():
    charges = []
    for vehicle_type, rate in HOURLY_RATES.items():
        charges.append({
            'vehicle_type': vehicle_type.value,
            'rate': rate
        })
    return jsonify({'success': True, 'charges': charges}), 200

# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/admin/dashboard', methods=['GET'])
def admin_dashboard():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    total_vehicles = len(parking_lot.vehicle_tickets)
    active_vehicles = sum(1 for t in parking_lot.tickets.values() if t.status.value == 'ACTIVE')
    total_payments = len(parking_lot.payments)
    total_revenue = sum(p.amount for p in parking_lot.payments)

    return jsonify({
        'success': True,
        'dashboard': {
            'total_vehicles_parked': total_vehicles,
            'active_vehicles': active_vehicles,
            'total_transactions': total_payments,
            'total_revenue': round(total_revenue, 2),
            'lot_info': {
                'lot_id': parking_lot.lot_id,
                'name': parking_lot.name,
                'address': parking_lot.address,
                'mobile': parking_lot.mobile
            }
        }
    }), 200

# ─────────────────────────────────────────────────────────────────────────────
# UPDATED: ADMIN REPORTS - TODAY, YESTERDAY, MONTHLY
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/admin/reports', methods=['GET'])
def admin_reports():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    month_start = datetime(today.year, today.month, 1).date()

    def filter_payments_by_date(payments, start_date, end_date=None):
        filtered = []
        for payment in payments:
            # Get the ticket entry time to determine when the vehicle was parked
            ticket = payment.ticket
            if ticket and ticket.entry_time:
                entry_date = ticket.entry_time.date()
                if end_date:
                    if start_date <= entry_date <= end_date:
                        filtered.append(payment)
                else:
                    if entry_date >= start_date:
                        filtered.append(payment)
        return filtered

    def generate_report_data(payments):
        by_vehicle_type = {}
        for payment in payments:
            ticket = payment.ticket
            if ticket:
                vtype = ticket.vehicle.vehicle_type.value
                if vtype not in by_vehicle_type:
                    by_vehicle_type[vtype] = {'count': 0, 'revenue': 0}
                by_vehicle_type[vtype]['count'] += 1
                by_vehicle_type[vtype]['revenue'] += payment.amount

        by_payment_method = {}
        for payment in payments:
            method = payment.method.value
            if method not in by_payment_method:
                by_payment_method[method] = {'count': 0, 'amount': 0}
            by_payment_method[method]['count'] += 1
            by_payment_method[method]['amount'] += payment.amount

        return {
            'by_vehicle_type': by_vehicle_type,
            'by_payment_method': by_payment_method,
            'total_revenue': round(sum(p.amount for p in payments), 2),
            'total_transactions': len(payments)
        }

    # Today's reports
    today_payments = filter_payments_by_date(parking_lot.payments, today)
    today_data = generate_report_data(today_payments)

    # Yesterday's reports
    yesterday_payments = filter_payments_by_date(parking_lot.payments, yesterday, yesterday)
    yesterday_data = generate_report_data(yesterday_payments)

    # Monthly reports
    month_payments = filter_payments_by_date(parking_lot.payments, month_start)
    month_data = generate_report_data(month_payments)

    return jsonify({
        'success': True,
        'reports': {
            'today': today_data,
            'yesterday': yesterday_data,
            'monthly': month_data
        }
    }), 200

@app.route('/api/admin/spot/add', methods=['POST'])
def add_parking_spot():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.json
    try:
        floor_number = int(data.get('floor_number'))
        spot_number = data.get('spot_number', '').strip()
        spot_type_str = data.get('spot_type', '')
        count = int(data.get('count', 1))
        
        spot_type = None
        for st in SpotType:
            if st.value == spot_type_str or st.name == spot_type_str:
                spot_type = st
                break
        
        if not spot_type:
            return jsonify({'success': False, 'message': f'Invalid Spot Type: {spot_type_str}'}), 400
            
        success = admin_manager.add_spot(floor_number, spot_number, spot_type, count)
        if success:
            return jsonify({'success': True, 'message': f'Successfully added {count} spot(s) to Floor {floor_number}'}), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to add spot(s)'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/admin/spot/remove', methods=['POST'])
def remove_parking_spot():
    if session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.json
    try:
        floor_number = int(data.get('floor_number'))
        spot_number = data.get('spot_number', '').strip()
        spot_type_str = data.get('spot_type', '')
        count = int(data.get('count', 1) or 1)
        
        spot_type = None
        for st in SpotType:
            if st.value == spot_type_str or st.name == spot_type_str:
                spot_type = st
                break
        if not spot_type:
            return jsonify({'success': False, 'message': f'Invalid Spot Type: {spot_type_str}'}), 400

        success = admin_manager.remove_spot(floor_number, spot_number, spot_type, count)
        if success:
            message = f'Successfully removed {count} spot(s) starting at {spot_number} from Floor {floor_number}'
            return jsonify({'success': True, 'message': message}), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to remove spot(s) (they may be occupied or not exist)'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/lot/floor/<int:floor_num>/spots', methods=['GET'])
def get_floor_spots(floor_num):
    floor = parking_lot.floors.get(floor_num)
    if not floor:
        return jsonify({'success': False, 'message': f'Floor {floor_num} not found'}), 404
        
    spots_data = []
    for idx, spot in enumerate(floor.spots, 1):
        vehicle_info = None
        if not spot.is_available:
            for ticket in parking_lot.tickets.values():
                if ticket.status == TicketStatus.ACTIVE and ticket.spot.spot_number == spot.spot_number:
                    vehicle_info = {
                        'vehicle_number': ticket.vehicle.vehicle_number,
                        'vehicle_type': ticket.vehicle.vehicle_type.value,
                        'owner_name': ticket.vehicle.owner_name,
                        'color': ticket.vehicle.color,
                        'entry_time': ticket.entry_time.isoformat()
                    }
                    break
                    
        spots_data.append({
            'spot_id': spot.spot_id,
            'spot_number': str(idx),
            'spot_type': spot.spot_type.value,
            'is_available': spot.is_available,
            'vehicle_info': vehicle_info
        })
        
    return jsonify({'success': True, 'floor_number': floor_num, 'spots': spots_data}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    debug = os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}
    app.run(debug=debug, host='0.0.0.0', port=port)