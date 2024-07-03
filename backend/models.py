# models.py
from config import db

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    terminal_id = db.Column(db.String(50), nullable=False, unique=True)  # Adding unique constraint
    physical_tid = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    merchant_name = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    group = db.Column(db.String(50), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'terminal_id': self.terminal_id,
            'physical_tid': self.physical_tid,
            'model': self.model,
            'merchant_name': self.merchant_name,
            'city': self.city,
            'group': self.group
            'branch': self.branch
        }

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    terminal_id = db.Column(db.String(50), db.ForeignKey('client.terminal_id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    volume = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)

    __table_args__ = (db.UniqueConstraint('terminal_id', 'date', name='_terminal_date_uc'),)

    def to_dict(self):
        return {
            'id': self.id,
            'terminal_id': self.terminal_id,
            'date': self.date.isoformat(),
            'volume': self.volume,
            'value': self.value
        }