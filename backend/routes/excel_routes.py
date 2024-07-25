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

#Daily Volumes and Values
@excel_routes_bp.route('/excel/getVolume_Value/<string:group_name>', methods=['GET'])
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

# Summary 
@excel_routes_bp.route('/excel/getDailySummary/<string:group_name>', methods=['GET'])
def calculate_daily_summary(group_name):
    try:
        # Query group clients
        clients = Client.query.filter_by(group=group_name).all()

        if not clients:
            return jsonify({'error': 'No clients found for this group'}), 404

        # Extract all terminal IDs
        terminal_ids = [client.terminal_id for client in clients]

        # Query all transactions for the group
        transactions = Transaction.query.filter(Transaction.terminal_id.in_(terminal_ids)).all()
        if not transactions:
            return jsonify({'error': 'No transactions found for this group'}), 404

        # Initialize a dictionary to store daily summary data
        daily_summary = {}

        # Process transactions to calculate daily summaries
        for transaction in transactions:
            date_str = transaction.date.date().isoformat()  # Get date as string
            if date_str not in daily_summary:
                daily_summary[date_str] = {
                    'Value in ZiG': 0,
                    'Volume in ZiG': 0,
                    'Value in USD': 0,
                    'Volume in USD': 0
                }

            # Determine currency based on terminal ID prefix
            if transaction.terminal_id.startswith(('SBM', 'ZPZ', 'C')):
                daily_summary[date_str]['Value in ZiG'] += transaction.value
                daily_summary[date_str]['Volume in ZiG'] += transaction.volume
            elif transaction.terminal_id.startswith(('FCM', 'FCZP')):
                daily_summary[date_str]['Value in USD'] += transaction.value
                daily_summary[date_str]['Volume in USD'] += transaction.volume

        # Convert daily summary dictionary to DataFrame
        summary_df = pd.DataFrame.from_dict(daily_summary, orient='index').reset_index()
        summary_df = summary_df.rename(columns={'index': 'date'})

        # Sort the DataFrame by date
        summary_df['date'] = pd.to_datetime(summary_df['date'])
        summary_df = summary_df.sort_values(by='date')
        summary_df['date'] = summary_df['date'].dt.date

        # Prepare Excel writer
        excel_filename = f'Summary{group_name}.xlsx'
        with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
            summary_df.to_excel(writer, sheet_name='summary', index=False)

        # Send the generated Excel file as a response with appropriate headers
        return send_file(excel_filename, as_attachment=True, download_name=excel_filename)
    except Exception as e:
        return jsonify({'error': f'Failed to calculate daily summary: {str(e)}'}), 500

#Cumulative trans 
@excel_routes_bp.route('/excel/cumulative/<string:group_name>', methods=['GET'])
def calculate_cumulative_transactions(group_name):
    try:
        # Query group clients
        clients = Client.query.filter_by(group=group_name).all()
        if not clients:
            return jsonify({'error': 'No clients found for this group'}), 404

        # Extract all terminal IDs and initialize summary dictionary
        terminal_ids = [client.terminal_id for client in clients]
        summary = {client.terminal_id: {'merchant_name': client.merchant_name, 'total_value': 0, 'total_volume': 0} for client in clients}

        # Query all transactions for the group
        transactions = Transaction.query.filter(Transaction.terminal_id.in_(terminal_ids)).all()

        # Populate summary dictionary with transaction data
        for transaction in transactions:
            summary[transaction.terminal_id]['total_value'] += transaction.value
            summary[transaction.terminal_id]['total_volume'] += transaction.volume

        # Convert summary dictionary to DataFrame
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

         # Prepare Excel writer
        excel_filename = f'Cumulative_{group_name}.xlsx'
        with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
            df_summary.to_excel(writer, sheet_name='summary', index=False)

        # Send the generated Excel file as a response with appropriate headers
        return send_file(excel_filename, as_attachment=True, download_name=excel_filename)

    except Exception as e:
        return jsonify({'error': f'Failed to calculate cumulative transactions: {str(e)}'}), 500

# Cumulative by branch
@excel_routes_bp.route('/excel/cumulative_by_branch/<string:group_name>', methods=['GET'])
def calculate_cumulative_transactions_by_branch(group_name):
    try:
        # Query group clients
        clients = Client.query.filter_by(group=group_name).all()
        if not clients:
            return jsonify({'error': 'No clients found for this group'}), 404

        # Extract terminal IDs and initialize summary dictionary
        terminal_ids = [client.terminal_id for client in clients]
        branch_summary = {}

        # Initialize branch summary with zero values
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

        # Query all transactions for the group
        transactions = Transaction.query.filter(Transaction.terminal_id.in_(terminal_ids)).all()

        # Populate summary dictionary with transaction data
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

        # Convert branch summary to DataFrame
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

        # Use a temporary directory to save the file
        file_name =  f'Cumulative_by_branch_{group_name}.xlsx'
        with pd.ExcelWriter(file_name, engine='xlsxwriter') as writer:
            df_summary.to_excel(writer, sheet_name='summary', index=False)

            # Send the generated Excel file as a response with appropriate headers
        return send_file(file_name, as_attachment=True, download_name=file_name)

    except Exception as e:
        return jsonify({'error': f'Failed to calculate cumulative transactions by branch: {str(e)}'}), 500

