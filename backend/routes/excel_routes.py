from flask import request, jsonify, send_file
from routes import excel_routes_bp
from config import db
from models import Client, Transaction
import pandas as pd
import io
import os
import xlsxwriter
import tempfile
from datetime import datetime

######################### Get Values and Volumes ##################################################

@excel_routes_bp.route('/excel/getVolume_Value/<string:group_name>', methods=['GET'])
def export_transactions_to_excel(group_name):
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

        unique_dates = sorted(set(transaction.date.date() for transaction in transactions))

        terminal_data = {terminal_id: {date: {'value': 0, 'volume': 0} for date in unique_dates} for terminal_id in terminal_ids}

        for transaction in transactions:
            date_key = transaction.date.date()
            terminal_data[transaction.terminal_id][date_key]['value'] += transaction.value
            terminal_data[transaction.terminal_id][date_key]['volume'] += transaction.volume

        df_value = pd.DataFrame(index=terminal_ids, columns=['Terminal ID'] + [str(date) for date in unique_dates])
        df_volume = pd.DataFrame(index=terminal_ids, columns=['Terminal ID'] + [str(date) for date in unique_dates])

        for terminal_id, data in terminal_data.items():
            df_value.at[terminal_id, 'Terminal ID'] = terminal_id
            df_volume.at[terminal_id, 'Terminal ID'] = terminal_id
            for date, values in data.items():
                df_value.at[terminal_id, str(date)] = values['value']
                df_volume.at[terminal_id, str(date)] = values['volume']

        excel_filename = f'transactions_{group_name}.xlsx'
        with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
            df_value.to_excel(writer, sheet_name='Value', index=False)
            df_volume.to_excel(writer, sheet_name='Volume', index=False)

        return send_file(excel_filename, as_attachment=True, download_name=excel_filename)

    except Exception as e:
        return jsonify({'error': f'Failed to export transactions to Excel: {str(e)}'}), 500


######################## Daily Summary ############################################
@excel_routes_bp.route('/excel/getDailySummary/<string:group_name>', methods=['GET'])
def calculate_daily_summary(group_name):
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

        daily_summary = {}

        for transaction in transactions:
            date_str = transaction.date.date().isoformat()
            if date_str not in daily_summary:
                daily_summary[date_str] = {
                    'Value in ZiG': 0,
                    'Volume in ZiG': 0,
                    'Value in USD': 0,
                    'Volume in USD': 0
                }

            if transaction.terminal_id.startswith(('SBM', 'ZPZ', 'C')):
                daily_summary[date_str]['Value in ZiG'] += transaction.value
                daily_summary[date_str]['Volume in ZiG'] += transaction.volume
            elif transaction.terminal_id.startswith(('FCM', 'FCZP')):
                daily_summary[date_str]['Value in USD'] += transaction.value
                daily_summary[date_str]['Volume in USD'] += transaction.volume

        summary_df = pd.DataFrame.from_dict(daily_summary, orient='index').reset_index()
        summary_df = summary_df.rename(columns={'index': 'date'})
        summary_df['date'] = pd.to_datetime(summary_df['date'])
        summary_df = summary_df.sort_values(by='date')
        summary_df['date'] = summary_df['date'].dt.date

        excel_filename = f'Summary_{group_name}.xlsx'
        with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
            summary_df.to_excel(writer, sheet_name='summary', index=False)

        return send_file(excel_filename, as_attachment=True, download_name=excel_filename)

    except Exception as e:
        print(f'Error: {str(e)}')  # Log the error
        return jsonify({'error': f'Failed to calculate daily summary: {str(e)}'}), 500
        
############################## Cumulative trans ####################################

@excel_routes_bp.route('/excel/cumulative/<string:group_name>', methods=['GET'])
def calculate_cumulative_transactions(group_name):
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
        summary = {client.terminal_id: {'merchant_name': client.merchant_name, 'total_value': 0, 'total_volume': 0} for client in clients}

        transactions = Transaction.query.filter(
            Transaction.terminal_id.in_(terminal_ids),
            Transaction.date.between(start_date, end_date)
        ).all()

        for transaction in transactions:
            summary[transaction.terminal_id]['total_value'] += transaction.value
            summary[transaction.terminal_id]['total_volume'] += transaction.volume

        summary_data = [
            {
                'Merchant_name': data['merchant_name'],
                'TerminalID': terminal_id,
                'Total Value': data['total_value'],
                'Total Volume': data['total_volume']
            }
            for terminal_id, data in summary.items()
        ]
        df_summary = pd.DataFrame(summary_data)

        excel_filename = f'Cumulative_{group_name}.xlsx'
        with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
            df_summary.to_excel(writer, sheet_name='summary', index=False)

        return send_file(excel_filename, as_attachment=True, download_name=excel_filename)

    except Exception as e:
        return jsonify({'error': f'Failed to calculate cumulative transactions: {str(e)}'}), 500
######################### By Branch ######################################

@excel_routes_bp.route('/excel/cumulative_by_branch/<string:group_name>', methods=['GET'])
def calculate_cumulative_transactions_by_branch(group_name):
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
        branch_summary = {}

        for client in clients:
            branch = client.branch
            if branch not in branch_summary:
                branch_summary[branch] = {
                    'num_terminals': 0,
                    'value_in_ZiG': 0,
                    'volume_in_ZiG': 0,
                    'value_in_USD': 0,
                    'volume_in_USD': 0
                }
            branch_summary[branch]['num_terminals'] += 1

        transactions = Transaction.query.filter(
            Transaction.terminal_id.in_(terminal_ids),
            Transaction.date.between(start_date, end_date)
        ).all()

        for transaction in transactions:
            for client in clients:
                if transaction.terminal_id == client.terminal_id:
                    branch = client.branch
                    if transaction.terminal_id.startswith(('SBM', 'ZPZ')):
                        branch_summary[branch]['value_in_ZiG'] += transaction.value
                        branch_summary[branch]['volume_in_ZiG'] += transaction.volume
                    elif transaction.terminal_id.startswith(('FCM', 'FCZP')):
                        branch_summary[branch]['value_in_USD'] += transaction.value
                        branch_summary[branch]['volume_in_USD'] += transaction.volume
                    break

        summary_data = [
            {
                'num of terminal IDs': data['num_terminals'],
                'Branch': branch,
                'Value in ZiG': data['value_in_ZiG'],
                'Volume in ZiG': data['volume_in_ZiG'],
                'Value in USD': data['value_in_USD'],
                'Volume in USD': data['volume_in_USD']
            }
            for branch, data in branch_summary.items()
        ]
        df_summary = pd.DataFrame(summary_data)

        file_name =  f'Cumulative_by_branch_{group_name}.xlsx'
        with pd.ExcelWriter(file_name, engine='xlsxwriter') as writer:
            df_summary.to_excel(writer, sheet_name='summary', index=False)

        return send_file(file_name, as_attachment=True, download_name=file_name)

    except Exception as e:
        return jsonify({'error': f'Failed to calculate cumulative transactions by branch: {str(e)}'}), 500

