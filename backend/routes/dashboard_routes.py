from flask import request, jsonify
from routes import dash_routes_bp
from config import db
from models import Transaction, Client
from datetime import datetime

@dash_routes_bp.route('/dashboard/data', methods=['GET'])
def get_dashboard_data():
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({'error': 'Start date and end date are required'}), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        groups = Client.query.with_entities(Client.group).distinct().all()
        group_names = [group[0] for group in groups]
        dashboard_data = {}

        for group_name in group_names:
            clients = Client.query.filter_by(group=group_name).all()
            terminal_ids_zig = [client.terminal_id for client in clients if client.terminal_id.startswith(('SBM', 'ZPZ'))]
            terminal_ids_usd = [client.terminal_id for client in clients if client.terminal_id.startswith(('FCM', 'FCZP'))]

            transactions = Transaction.query.filter(
                Transaction.terminal_id.in_([client.terminal_id for client in clients]),
                Transaction.date.between(start_date, end_date)
            ).all()

            total_value_zig = 0
            total_volume_zig = 0
            total_value_usd = 0
            total_volume_usd = 0
            active_terminals_zig = set()
            active_terminals_usd = set()

            for transaction in transactions:
                if transaction.terminal_id.startswith(('SBM', 'ZPZ')):
                    total_value_zig += transaction.value
                    total_volume_zig += transaction.volume
                    if transaction.value > 0:
                        active_terminals_zig.add(transaction.terminal_id)
                elif transaction.terminal_id.startswith(('FCM', 'FCZP')):
                    total_value_usd += transaction.value
                    total_volume_usd += transaction.volume
                    if transaction.value > 0:
                        active_terminals_usd.add(transaction.terminal_id)

            activity_ratio_zig = len(active_terminals_zig) / len(terminal_ids_zig) if terminal_ids_zig else 0
            activity_ratio_usd = len(active_terminals_usd) / len(terminal_ids_usd) if terminal_ids_usd else 0

            dashboard_data[group_name] = {
                'total_value_zig': total_value_zig,
                'total_volume_zig': total_volume_zig,
                'total_value_usd': total_value_usd,
                'total_volume_usd': total_volume_usd,
                'activity_ratio_zig': activity_ratio_zig,
                'activity_ratio_usd': activity_ratio_usd
            }

        return jsonify(dashboard_data)

    except Exception as e:
        return jsonify({'error': f'Failed to fetch dashboard data: {str(e)}'}), 500
