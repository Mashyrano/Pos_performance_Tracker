# main.py
from flask import request, jsonify, send_file
from config import app, db
from models import Client
from models import Transaction
import pandas as pd
import io
from datetime import datetime
import xlsxwriter

##################### Client Route #######################
# create client
@app.route('/clients', methods=['POST'])
def add_client():
    data = request.json
    new_client = Client(
        terminal_id=data['terminal_id'],
        physical_tid=data['physical_tid'],
        model=data['model'],
        merchant_name=data['merchant_name'],
        city=data['city'],
        group=data['group']
    )
    db.session.add(new_client)
    db.session.commit()
    return jsonify(new_client.to_dict()), 201

# get all clients
@app.route('/clients', methods=['GET'])
def get_clients():
    clients = Client.query.all()
    return jsonify([client.to_dict() for client in clients]), 200

#get all groups
@app.route('/clients/groups', methods=['GET'])
def get_client_groups():
    try:
        # Query all distinct group names from the clients table
        groups = db.session.query(Client.group).distinct().all()
        group_names = [group[0] for group in groups]  # Extracting group names from query result
        
        return jsonify({'groups': group_names}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# update a client
@app.route('/clients/<int:id>', methods=['PUT'])
def update_client(id):
    data = request.json
    client = Client.query.get_or_404(id)
    client.terminal_id = data['terminal_id']
    client.physical_tid = data['physical_tid']
    client.model = data['model']
    client.merchant_name = data['merchant_name']
    client.city = data['city']
    client.group = data['group']
    db.session.commit()
    return jsonify(client.to_dict()), 200

# delete client
@app.route('/clients/<int:id>', methods=['DELETE'])
def delete_client(id):
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    return '', 204

# create clients by uploading excel file
@app.route('/clients/upload', methods=['POST'])
def upload_clients():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and file.filename.endswith('.xlsx'):
        stream = io.BytesIO(file.read())
        df = pd.read_excel(stream)

        success_count = 0
        error_messages = []

        for _, row in df.iterrows():
            terminal_id = row['Terminal Id']
            
            # Check if terminal_id already exists in the database
            existing_client = Client.query.filter_by(terminal_id=terminal_id).first()
            if existing_client:
                error_messages.append(f"Client with terminal ID '{terminal_id}' already exists, skipping.")
                continue
            
            # Create a new client object and add it to the session
            new_client = Client(
                terminal_id=terminal_id,
                physical_tid=row['Physical TId'],
                model=row['Model'],
                merchant_name=row['Merchant Name'],
                city=row['City'],
                group=row['Group']
            )
            db.session.add(new_client)
            success_count += 1
        
        try:
            db.session.commit()
            message = f'{success_count} clients added successfully!'
            if error_messages:
                message += ' Some clients were skipped due to existing terminal IDs.'
            return jsonify({'message': message}), 201
        
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to add clients: {str(e)}'}), 500

    return jsonify({'error': 'Invalid file format or empty file'}), 400
# delete by group
@app.route('/clients/group/<string:group_name>', methods=['DELETE'])
def delete_group(group_name):
	# delete the transaction associated with group first
    delete_transactions_by_group(group_name)
	# delete from clients
    clients = Client.query.filter_by(group=group_name).all()
    if not clients:
        return jsonify({'error': 'Group not found'}), 404
    
    for client in clients:
        db.session.delete(client)
    db.session.commit()
    return jsonify({'message': f'All clients in group {group_name} deleted successfully!'}), 200


############################## Transactions routes #####################################################
#################################################################################################

# upload transactions

@app.route('/transactions/upload', methods=['POST'])
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
@app.route('/transactions/<string:terminal_id>', methods=['GET'])
def get_transactions(terminal_id):
    transactions = Transaction.query.filter_by(terminal_id=terminal_id).all()
    if not transactions:
        return jsonify({'error': 'No transactions found for this terminal ID'}), 404
    return jsonify([transaction.to_dict() for transaction in transactions]), 200

# Get all transactions
@app.route('/transactions', methods=['GET'])
def get_all_transactions():
    transactions = Transaction.query.all()
    return jsonify([transaction.to_dict() for transaction in transactions]), 200


# delete transactions by group
@app.route('/transactions/group/<string:group_name>', methods=['DELETE'])
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

# get transactions of a particular group
@app.route('/transactions/group/<string:group_name>', methods=['GET'])
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

################################### Special Routes for excel #################################################
#################################################################################################

@app.route('/transactions/excel-export/<string:group_name>', methods=['GET'])
def export_transactions_to_excel(group_name):
    try:
        # Query group clients
        clients = Client.query.filter_by(group=group_name).all()

        if not clients:
            return jsonify({'error': 'No clients found for this group'}), 404

        # Extract all terminal IDs
        terminal_ids = [client.terminal_id for client in clients]

        # Query all transactions for the group
        transactions = Transaction.query.filter(Transaction.terminal_id.in_(terminal_ids)).all()

        # Determine unique dates from transactions
        unique_dates = sorted(set(transaction.date.date() for transaction in transactions))

        # Prepare a dictionary to store data for each terminal ID
        terminal_data = {terminal_id: {date: {'value': 0, 'volume': 0} for date in unique_dates} for terminal_id in terminal_ids}

        # Populate the dictionary with transaction data
        for transaction in transactions:
            date_key = transaction.date.date()
            terminal_data[transaction.terminal_id][date_key]['value'] += transaction.value
            terminal_data[transaction.terminal_id][date_key]['volume'] += transaction.volume

        # Create DataFrame for Value and Volume sheets
        df_value = pd.DataFrame(index=terminal_ids, columns=['Terminal ID'] + [str(date) for date in unique_dates])
        df_volume = pd.DataFrame(index=terminal_ids, columns=['Terminal ID'] + [str(date) for date in unique_dates])

        # Populate DataFrames with transaction values
        for terminal_id, data in terminal_data.items():
            df_value.at[terminal_id, 'Terminal ID'] = terminal_id
            df_volume.at[terminal_id, 'Terminal ID'] = terminal_id
            for date, values in data.items():
                df_value.at[terminal_id, str(date)] = values['value']
                df_volume.at[terminal_id, str(date)] = values['volume']

        # Prepare Excel writer
        excel_filename = f'transactions_{group_name}.xlsx'
        with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
            df_value.to_excel(writer, sheet_name='Value', index=False)
            df_volume.to_excel(writer, sheet_name='Volume', index=False)

        # Send the generated Excel file as a response with appropriate headers
        return send_file(excel_filename, as_attachment=True, download_name=excel_filename)

    except Exception as e:
        return jsonify({'error': f'Failed to export transactions to Excel: {str(e)}'}), 500


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
