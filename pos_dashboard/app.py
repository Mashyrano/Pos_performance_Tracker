from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests

app = Flask(__name__)

BACKEND_URL = 'http://localhost:5000'  # URL of the backend server

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

############################ Clients #############################
# client routes...
@app.route('/add_client', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        client_data = {
            'merchant_name': request.form['merchant_name'],
            'terminal_id': request.form['terminal_id'],
            'physical_tid': request.form['physical_tid'],
            'model': request.form['model'],
            'city': request.form['city'],
            'group': request.form['group'],
            'branch': request.form['branch']
        }
        response = requests.post(f'{BACKEND_URL}/clients', json=client_data)
        if response.status_code == 201:
            return redirect(url_for('clients'))
        else:
            return jsonify({'error': 'Failed to add client'}), 400

    return render_template('add_client.html')

@app.route('/upload_clients', methods=['POST'])
def upload_clients():
    file = request.files['file']
    if file:
        files = {'file': (file.filename, file.stream, file.mimetype)}
        response = requests.post(f'{BACKEND_URL}/clients/upload', files=files)
        if response.status_code == 201:
            return redirect(url_for('clients', message=response.json().get('message')))
        else:
            return jsonify({'error': 'Failed to upload clients'}), 400
    return jsonify({'error': 'No file uploaded'}), 400

@app.route('/upload_clients_page')
def upload_clients_page():
    return render_template('upload_clients.html')

@app.route('/edit_client/<int:id>', methods=['GET', 'POST'])
def edit_client(id):
    if request.method == 'POST':
        client_data = {
            'merchant_name': request.form['merchant_name'],
            'terminal_id': request.form['terminal_id'],
            'physical_tid': request.form['physical_tid'],
            'model': request.form['model'],
            'city': request.form['city'],
            'group': request.form['group'],
            'branch': request.form['branch']
        }
        response = requests.put(f'{BACKEND_URL}/clients/{id}', json=client_data)
        if response.status_code == 200:
            return redirect(url_for('clients'))
        else:
            return jsonify({'error': 'Failed to update client'}), 400

    response = requests.get(f'{BACKEND_URL}/clients/{id}')
    try:
        client = response.json()
    except requests.exceptions.JSONDecodeError:
        client = None

    if client is None:
        return jsonify({'error': 'Client not found'}), 404

    return render_template('edit_client.html', client=client)


@app.route('/delete_client/<int:id>', methods=['POST'])
def delete_client(id):
    response = requests.delete(f'{BACKEND_URL}/clients/{id}')
    if response.status_code == 204:
        return redirect(url_for('clients'))
    else:
        return jsonify({'error': 'Failed to delete client'}), 400

@app.route('/clients')
def clients():
    group = request.args.get('group')
    message = request.args.get('message')
    if group:
        response = requests.get(f'{BACKEND_URL}/clients/get_group/{group}')
    else:
        response = requests.get(f'{BACKEND_URL}/clients')

    try:
        clients = response.json()
    except requests.exceptions.JSONDecodeError:
        clients = []

    return render_template('clients.html', clients=clients, group_filter=group, message=message)


################# Groups #################################

@app.route('/groups')
def groups():
    response = requests.get(f'{BACKEND_URL}/clients/groups')
    groups = response.json().get('groups', [])
    return render_template('groups.html', groups=groups)

@app.route('/delete_group/<string:group_name>', methods=['POST'])
def delete_group(group_name):
    response = requests.delete(f'{BACKEND_URL}/clients/group/{group_name}')
    if response.status_code == 200:
        return redirect(url_for('groups'))
    else:
        return jsonify({'error': 'Failed to delete group'}), 400

#################### Transactions #####################################
# transactions routes
@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    message = ''
    group = ''
    start_date = ''
    end_date = ''
    total_volume = 0
    total_value = 0

    if request.method == 'POST':
        if 'file' in request.files:
            # Handle file upload
            file = request.files['file']
            if file:
                files = {'file': (file.filename, file.stream, file.mimetype)}
                response = requests.post(f'{BACKEND_URL}/transactions/upload', files=files)
                if response.status_code == 201:
                    message = response.json().get('message', 'Transactions uploaded successfully!')
                else:
                    message = response.json().get('error', 'Failed to upload transactions')
        else:
            # Handle date range and group filtering
            group = request.form['group']
            start_date = request.form['start_date']
            end_date = request.form['end_date']

            response = requests.get(f'{BACKEND_URL}/transactions/group_summary/{group}', params={
                'start_date': start_date,
                'end_date': end_date
            })

            if response.status_code == 200:
                data = response.json()
                total_volume = data.get('total_volume', 0)
                total_value = data.get('total_value', 0)
            else:
                message = response.json().get('error', 'Failed to fetch transactions')

    groups_response = requests.get(f'{BACKEND_URL}/clients/groups')
    groups = groups_response.json().get('groups', [])

    return render_template('transactions.html', group=group, start_date=start_date, end_date=end_date, total_volume=total_volume, total_value=total_value, groups=groups, message=message)

################# Reports ##########################
#reports
@app.route('/reports', methods=['GET'])
def reports():
    groups_response = requests.get(f'{BACKEND_URL}/clients/groups')
    groups = groups_response.json().get('groups', [])
    return render_template('reports.html', groups=groups)


if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Change port if necessary
