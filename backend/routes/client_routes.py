from flask import request, jsonify
from routes import client_bp
from config import db
from models import Client
from routes.transaction_routes import delete_transactions_by_group, delete_all_transactions
import pandas as pd
import io

#add a client
@client_bp.route('/clients', methods=['POST'])
def add_client():

    data = request.json

    # Check if terminal_id already exists in the database
    existing_client = Client.query.filter_by(terminal_id=data['terminal_id']).first()
    if existing_client:
        error_messages = ''
        error_messages.append(f"Client with terminal ID '{data['terminal_id']}' already exists, skipped.")
        return jsonify({'message': error_messages}), 500

    new_client = Client(
        terminal_id=data['terminal_id'],
        physical_tid=data['physical_tid'],
        model=data['model'],
        merchant_name=data['merchant_name'],
        city=data['city'],
        group=data['group'],
        branch=data['branch']
    )
    db.session.add(new_client)
    db.session.commit()
    return jsonify(new_client.to_dict()), 201

#get all clients
@client_bp.route('/clients', methods=['GET'])
def get_clients():
    clients = Client.query.all()
    return jsonify([client.to_dict() for client in clients]), 200

#get all groups
@client_bp.route('/clients/groups', methods=['GET'])
def get_client_groups():
    try:
        # Query all distinct group names from the clients table
        groups = db.session.query(Client.group).distinct().all()
        group_names = [group[0] for group in groups]  # Extracting group names from query result
        
        return jsonify({'groups': group_names}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# update a client
@client_bp.route('/clients/<int:id>', methods=['PUT'])
def update_client(id):
    data = request.json
    client = Client.query.get_or_404(id)
    client.terminal_id = data['terminal_id']
    client.physical_tid = data['physical_tid']
    client.model = data['model']
    client.merchant_name = data['merchant_name']
    client.city = data['city']
    client.group = data['group']
    client.branch = data['branch']
    db.session.commit()
    return jsonify(client.to_dict()), 200

# delete client
@client_bp.route('/clients/<int:id>', methods=['DELETE'])
def delete_client(id):
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    return '', 204

# create clients by uploading excel file
@client_bp.route('/clients/upload', methods=['POST'])
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
                group=row['Group'],
                branch=row['Branch']
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
@client_bp.route('/clients/group/<string:group_name>', methods=['DELETE'])
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

@client_bp.route('/clients/delete/all', methods=['DELETE'])
def delete_all():
    # delete the transaction associated with group first
    delete_all_transactions()
    # delete from clients
    clients = Client.query.all()
    if not clients:
        return jsonify({'error': 'No Client found'}), 404
    
    for client in clients:
        db.session.delete(client)
    db.session.commit()
    return jsonify({'message': f'All clients deleted successfully!'}), 200