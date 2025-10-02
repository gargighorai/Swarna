from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
db = SQLAlchemy()
from flask_login import UserMixin
advice_drugs_association = db.Table(
    'advice_drugs',
    db.Column('advice_id', db.Integer, db.ForeignKey('advice.id')),
    db.Column('drug_id', db.Integer, db.ForeignKey('drug.id'))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=False, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    doc_mob = db.Column(db.String(20), unique=True, nullable=True)
    degree = db.Column(db.String(100), nullable=True)
    website = db.Column(db.String(100), nullable=True)
    reg_no = db.Column(db.String(70), unique=True, nullable=True)
    
    patients = db.relationship('Patient', backref='owner', lazy='dynamic')
    def __repr__(self):
        return f'<User {self.username}>'

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(100))
    address = db.Column(db.String(100))
    mob_no = db.Column(db.String(30))
    date_of_entry = db.Column(db.DateTime, default=datetime.utcnow)   
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    advice = db.relationship('Advice', backref='patient')
    
    def __repr__(self):
        return f'<Patient {self.name}>'

class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    def __repr__(self):
        return f"Drug ('{self.name}')"

class Advice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'))
    prescribed_drugs = db.relationship(
        'Drug',
        secondary=advice_drugs_association,
        backref=db.backref('advised', lazy='dynamic')
    )
    def __repr__(self):
        return f'<Advice {self.id}>'
