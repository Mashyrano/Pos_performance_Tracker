from flask import request, jsonify
from routes import transaction_bp
from config import db
from models import Transaction, Client
import pandas as pd
import io
from datetime import datetime

#Upload 
@transaction_bp.route('/transactions/upload', methods=['POST'])
def upload_transactions():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        stream = io.BytesIO(file.read())
        xl = pd.ExcelFile(stream)

        try:
            clients = {client.terminal_id: client for client in Client.query.all()}
            
            for sheet_name in xl.sheet_names:
                df = xl.parse(sheet_name)
                
                for _, row in df.iterrows():
                    terminal_id = row['TerminalID']
                    
                    if terminal_id in clients:
                        # Convert 'LastSeen' to a datetime object
                        last_seen = datetime.strptime(row['LastSeen'], '%Y-%m-%d %H:%M:%S.%f')

                        transaction = Transaction(
                            terminal_id=terminal_id,
                            date=last_seen,
                            volume=row['SalesCount'],
                            value=row['SumofSales']
                        )
                        db.session.merge(transaction)
            
            db.session.commit()
            return jsonify({'message': 'Transactions added successfully!'}), 201
        
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to add transactions: {str(e)}'}), 500

    return jsonify({'error': 'Invalid file format or empty file'}), 400

# Get all transactions for a specific terminal
@transaction_bp.route('/transactions/<string:terminal_id>', methods=['GET'])
def get_transactions(terminal_id):
    transactions = Transaction.query.filter_by(terminal_id=terminal_id).all()
    if not transactions:
        return jsonify({'error': 'No transactions found for this terminal ID'}), 404
    return jsonify([transaction.to_dict() for transaction in transactions]), 200

# Get all transactions
@transaction_bp.route('/transactions', methods=['GET'])
def get_all_transactions():
    transactions = Transaction.query.all()
    return jsonify([transaction.to_dict() for transaction in transactions]), 200

# delete transactions by group
@transaction_bp.route('/transactions/group/<string:group_name>', methods=['DELETE'])
def delete_transactions_by_group(group_name):
    try:
        # Query clients belonging to the specified group
        clients = Client.query.filter_by(group=group_name).all()

        if not clients:
            return jsonify({'error': 'Group not found'}), 404

        # Extract terminal IDs of clients in the group
        terminal_ids = [client.terminal_id for client in clients]

        # Query transactions associated with the extracted terminal IDs and group
        transactions = Transaction.query.filter(Transaction.terminal_id.in_(terminal_ids)).all()

        if not transactions:
            return jsonify({'error': 'No transactions found for this group'}), 404

        # Delete transactions associated with the extracted terminal IDs
        for transaction in transactions:
            db.session.delete(transaction)

        db.session.commit()
        return jsonify({'message': f'All transactions for group {group_name} deleted successfully!'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete transactions: {str(e)}'}), 500

#get transactions of a particular group
@transaction_bp.route('/transactions/group/<string:group_name>', methods=['GET'])
def get_group_transactions(group_name):
    try:
        # Query clients belonging to the specified group
        clients = Client.query.filter_by(group=group_name).all()

        if not clients:
            return jsonify({'error': 'Group not found'}), 404

        # Extract terminal IDs of clients in the group
        terminal_ids = [client.terminal_id for client in clients]

        # Query transactions associated with the extracted terminal IDs
        transactions = Transaction.query.filter(Transaction.terminal_id.in_(terminal_ids)).all()

        if not transactions:
            return jsonify({'message': 'No transactions found for this group'}), 200

        # Prepare JSON response with transaction data
        transactions_data = []
        for transaction in transactions:
            transactions_data.append({
                'terminal_id': transaction.terminal_id,
                'date': transaction.date.isoformat(),
                'volume': transaction.volume,
                'value': transaction.value
            })

        return jsonify({'transactions': transactions_data}), 200

    except Exception as e:
        return jsonify({'error': f'Failed to fetch transactions: {str(e)}'}), 500

# delete all transactions 
@transaction_bp.route('/transactions/delete/all', methods=['DELETE'])
def delete_all_transactions():
    try:
        # Query transactions 
        transactions = Transaction.query.all()

        if not transactions:
            return jsonify({'error': 'No transactions found'}), 404

        # Delete transactions associated with the extracted terminal IDs
        for transaction in transactions:
            db.session.delete(transaction)

        db.session.commit()
        return jsonify({'message': f'All transactions deleted successfully!'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete transactions: {str(e)}'}), 500


# Get transactions by group and date range
@transaction_bp.route('/transactions/group_summary/<string:group_name>', methods=['GET'])
def get_group_transactions_dates(group_name):
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

        clients = Client.query.filter_by(group=group_name).all()

        if not clients:
            return jsonify({'error': 'No clients found for this group'}), 404

        terminal_ids = [client.terminal_id for client in clients]

        transactions = Transaction.query.filter(
            Transaction.terminal_id.in_(terminal_ids),
            Transaction.date.between(start_date, end_date)
        ).all()

        if not transactions:
            return jsonify({'error': 'No transactions found for this group'}), 404

        total_value_zig = 0
        total_volume_zig = 0
        total_value_usd = 0
        total_volume_usd = 0

        for transaction in transactions:
            if transaction.terminal_id.startswith(('SBM', 'ZPZ', 'SQL')):
                total_value_zig += transaction.value
                total_volume_zig += transaction.volume
            elif transaction.terminal_id.startswith(('FCM', 'FCZP', 'FCQ')):
                total_value_usd += transaction.value
                total_volume_usd += transaction.volume

        return jsonify({
            'total_value_zig': total_value_zig,
            'total_volume_zig': total_volume_zig,
            'total_value_usd': total_value_usd,
            'total_volume_usd': total_volume_usd
        })

    except Exception as e:
        return jsonify({'error': f'Failed to fetch transactions: {str(e)}'}), 50


# delete between dates
@transaction_bp.route('/transactions/delete', methods=['POST'])
def delete_transactions():
    try:
        data = request.json
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({'error': 'Start date and end date are required'}), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        transactions_to_delete = Transaction.query.filter(
            Transaction.date.between(start_date, end_date)
        ).all()

        if not transactions_to_delete:
            return jsonify({'message': 'No transactions found for the specified date range'}), 404

        for transaction in transactions_to_delete:
            db.session.delete(transaction)

        db.session.commit()
        return jsonify({'message': f'{len(transactions_to_delete)} transactions deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': f'Failed to delete transactions: {str(e)}'}), 500