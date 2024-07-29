# main.py
from flask import request, jsonify
from config import app, db
from routes import client_bp, transaction_bp, excel_routes_bp, dash_routes_bp

# Register blueprints
app.register_blueprint(client_bp)
app.register_blueprint(transaction_bp)
app.register_blueprint(excel_routes_bp)
app.register_blueprint(dash_routes_bp)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
