# Standard Library imports
import io
import os
import json
from datetime import date
from io import BytesIO
from datetime import datetime
# Third-party imports
import docx
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from flask import Flask, jsonify, render_template, request, redirect, send_file, url_for, flash,Blueprint
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload
from docx import Document
from docx.shared import Inches,Pt,Cm,RGBColor
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH,WD_TAB_ALIGNMENT, WD_TAB_LEADER
from models import db, User, Patient, Advice, Drug
#---------------------------------
# App setup
# ---------------------------
# Configure your upload folder
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'json'}
app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Essential configurations
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+ os.path.join(basedir, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Set this to False
app.config['SECRET_KEY'] = "new-secret-key" # This is critical
app.config['DEBUG'] = True  # Enable debug mode for development

db.init_app(app)

# Create the upload folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Helper Function to Apply Shading (Background Color) ---
def set_cell_text(cell, text, rgb_tuple=None):
    cell.text=""
    p=cell.paragraphs[0]
    run = p.add_run(text)
    if rgb_tuple:
        run.font.color.rgb = RGBColor(*rgb_tuple)
def format_table_header(table, bg="0070C0", text=(255, 255, 255)):
    hdr_cells = table.rows[0].cells
    for cell in hdr_cells:
        # Save original text
        original_text = cell.text.strip()
        cell.text = ""  # clear
        run = cell.paragraphs[0].add_run(original_text)
        run.font.color.rgb = RGBColor(*text)
        # Set background
        set_cell_background(cell, bg)
def set_cell_background(cell, color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color)
    tcPr.append(shd)

# Initialize extensions
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)
# ---------------------------
# Flask-Login
# ---------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
# Assuming your DRUG_FILE is already defined at the top of your file
DRUG_FILE = os.path.join("static", "drugs.json")

def load_drugs_from_static_file():
    imported_count = 0
    try:
        with open(DRUG_FILE, "r") as file:
            drugs_data = json.load(file)
            for drug_entry in drugs_data:
                name = drug_entry.get('name')
                if name:
                    existing = Drug.query.filter_by(name=name).first()
                    if not existing:
                        db.session.add(Drug(name=name))
                        imported_count += 1
            db.session.commit()
    except FileNotFoundError:
        db.session.rollback()
        print(f"Error: The file '{DRUG_FILE}' was not found.")
        return 0
    except Exception as e:
        db.session.rollback()
        print(f"An unexpected error occurred while loading drugs: {e}")
        return 0
    return imported_count

@app.route('/import_static_drugs')
def import_static_drugs():
    imported_count = load_drugs_from_static_file()    
    if imported_count > 0:
        flash(f"Successfully imported {imported_count} new drugs.", 'success')
    else:
        flash("No new drugs were imported. The database may already be up to date.", 'info')
    return redirect(url_for('admin_drugs'))

# This is the route you want to redirect to
@app.route('/admin/drugs')
def admin_drugs():
    # ... your code to fetch drugs and render the template
    return render_template('admin_drugs.html')
# A function to import drugs directly into your database
@app.route('/admin/drugs/import_drugs', methods=['POST'])
@login_required
def import_drugs():
# 1. Handle file upload
    if 'drugs_file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('manage_drugs'))   
    file = request.files['drugs_file']   
    if file.filename == '':
        flash('No selected file', 'warning')
        return redirect(url_for('manage_drugs'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
       # 2. Save the uploaded file temporarily
        try:
            file.save(filepath)           
            # 3. Process the file and import to database
            imported_count = import_json_to_db(filepath)           
            if imported_count > 0:
                flash(f'Successfully imported {imported_count} drugs.', 'success')
            else:
                flash('No valid drugs found in the file.', 'warning')            
        except Exception as e:
            flash(f'An error occurred during import: {e}', 'danger')
            return redirect(url_for('manage_drugs'))            
        finally:
            # 4. Clean up the temporary file
            if os.path.exists(filepath):
                os.remove(filepath)        
        return redirect(url_for('manage_drugs'))
    flash('Invalid file type.', 'danger')
    return redirect(url_for('manage_drugs'))
# A helper function to do the database import
def import_json_to_db(filepath):
    imported_count = 0    
    try:
        with open(filepath, 'r') as f:
            drugs_data = json.load(f)
            
        for drug_entry in drugs_data:
            try:
                # Use .get() to handle missing keys gracefully
                name = drug_entry.get('name')
                
                # Ensure the name is not None before proceeding
                if not name:
                    continue
                
                # Check if a drug with the same name already exists
                existing_drug = Drug.query.filter_by(name=name).first()
                if existing_drug:
                    # You could update it here, or just skip it
                    print(f"Skipping duplicate drug: {name}")
                    continue
                
                new_drug = Drug(name=name)
                db.session.add(new_drug)
                imported_count += 1
                
            except Exception as e:
                # Rollback on a per-entry basis
                db.session.rollback()
                print(f"Failed to import a drug entry: {e}")
                
        db.session.commit()
    
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"File processing error: {e}")
        db.session.rollback()
        
    return imported_count

@app.route('/admin/drugs')
@login_required
def manage_drugs():
    drugs = Drug.query.order_by(Drug.name).all()
    return render_template("admin_drugs.html", drugs=drugs)
@app.route("/add_drugs")
@app.route('/admin/drugs/delete/<int:drug_id>', methods=["POST"])
@login_required
def delete_drug(drug_id):
    drug = Drug.query.get_or_404(drug_id)
    db.session.delete(drug)
    db.session.commit()
    flash("Drug deleted", "danger")
    return redirect(url_for("manage_drugs"))
@app.route('/admin/drugs/edit/<int:drug_id>', methods=["POST"])
@login_required
def edit_drug(drug_id):
    drug = Drug.query.get_or_404(drug_id)
    new_name = request.form.get("name", "").strip()
    if new_name:
        if not Drug.query.filter_by(name=new_name).first():
            drug.name = new_name
            db.session.commit()
            flash("Drug updated successfully.", "success")
        else:
            flash("Drug with this name already exists.", "warning")
    else:
        flash("Invalid drug name.", "danger")
    return redirect(url_for("manage_drugs"))
@app.route('/admin/drugs/export')
@login_required
def export_drugs():
    drugs = Drug.query.all()
    data = [{"id": drug.id, "name": drug.name} for drug in drugs]
    response = app.response_class(
        response=json.dumps(data, indent=2),
        mimetype='application/json'
    )
    response.headers.set("Content-Disposition", "attachment", filename="drugs.json")
    return response
# ---------------------------
# Routes for user authentication 
# ---------------------------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route('/')
def index():
    try:
        patients= Patient.query.options(joinedload(Patient.advice).joinedload(Advice.prescribed_drugs)).all()
        flash("Eager loading is working correctly!","success")
        return "your"
    except Exception as e:
        return f"database error: {e}" ,500
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Manually get data from the form
        username = request.form['username']
        email = request.form['email']
        password = request.form['password_hash']
        degree = request.form['degree']
        doc_mob = request.form['doc_mob']
        reg_no = request.form['reg_no']
        website = request.form['website']

        # Manual validation (you must add more checks here)
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        # Check for existing users
        user_by_username = User.query.filter_by(username=username).first()
        user_by_email = User.query.filter_by(email=email).first()
        if user_by_username or user_by_email:
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('register'))
        # Hash the password
        hashed_password = generate_password_hash(password)
        # Create and save the new user
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            degree=degree,
            doc_mob=doc_mob,
            reg_no=reg_no,
            website=website
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')
    
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password_hash = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password_hash):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard")
#@login_required
def dashboard():
    patients = Patient.query.filter_by(user_id=current_user.id).all()
    advices=Patient.query.filter_by(user_id=current_user.id).all()   
    return render_template("dashboard.html", patients=patients,advices=advices)
# --------Routes for patient management ------------
@app.route("/add_patient", methods=["GET", "POST"])
@login_required
def add_patient():
    if request.method == "POST":
        name = request.form["name"]
        age = request.form.get("age")
        gender = request.form.get("gender")
        mob_no= request.form.get("mob_no")
        address= request.form.get("address")
        new_patient = Patient(
                          name=name, 
                          age=age,
                          gender=gender,
                          mob_no=mob_no,
                          address=address,
                          user_id=current_user.id)
        db.session.add(new_patient)
        db.session.commit()
        # Redirect the user to the dashboard route
        return redirect(url_for('dashboard'))
    
    return render_template("add_patient.html")
from datetime import date
@app.route('/patient_profile/<int:patient_id>')
def patient_profile(patient_id):
    # Find the patient by ID.
    patients=Patient.query.get_or_404(patient_id)
    today=date.today()   
    return render_template('patient_profile.html', patient=patients, today=today)

@app.route('/print_advice/<int:advice_id>')
def print_advice(advice_id):
    now=date.today()
    patient = Patient.query.options(db.joinedload(Patient.advice).joinedload(Advice.prescribed_drugs)).get_or_404(advice_id)
    advice = Advice.query.options(db.joinedload(Advice.prescribed_drugs)).get_or_404(advice_id)
    return render_template('print_advice.html',patient=patient, advice=advice,today=now)

@app.route('/delete_advice/<int:advice_id>', methods=['POST'])
def delete_advice(advice_id):
    advice_to_delete = Advice.query.get_or_404(advice_id)
    
    patient_id = advice_to_delete.patient_id
    
    # Delete the advice from the database
    db.session.delete(advice_to_delete)
    db.session.commit()
    
    flash("Advice deleted successfully!", "success")
    return redirect(url_for('patient_profile', patient_id=patient_id))
@app.route("/delete_patient/<int:patient_id>",methods=["GET","POST"])
@login_required
def delete_patient(patient_id):
    patient= Patient.query.get_or_404(patient_id)
    db.session.delete(patient)
    db.session.commit()
    flash("Patient data deleted","success")
    return redirect(url_for("dashboard"))

@app.route('/full_advice/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def full_advice(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    drugs = Drug.query.all()

    if request.method == 'POST':
        notes = request.form.get('notes')
        prescribed_drugs = request.form.get('prescribed_drugs')
        prescribed_drugs = json.loads(prescribed_drugs) if prescribed_drugs else []

        # Save advice
        advice = Advice(patient_id=patient.id, doctor_id=current_user.id, notes=notes)
        db.session.add(advice)
        db.session.commit()
        # Save prescribed drugs
        db.session.commit()

        flash("Advice saved successfully!", "success")
        return redirect(url_for('dashboard'))

    return render_template('print_full_advice.html', patient=patient, drugs=drugs)    
from datetime import datetime

#--------Certificate and Receipt Routes ------------
from datetime import datetime
@app.route('/certificate/',methods=['GET', 'POST'])
@login_required
def certificate():
    return render_template('death_certificate.html',
            now=datetime.now())
@app.route("/certificate/medical")
@login_required
def medical_certificate():
    now=datetime.now()
    return render_template("certificate/medical_certificate.html",
                           now=datetime.now())

@app.route("/certificate/fitness")
@login_required
def fitness_certificate():
    return render_template("certificate/fitness_certificate.html")

@app.route("/certificate/custom")
@login_required
def custom_certificate():
    return render_template("certificate/custom_certificate.html")

@app.route('/receipt')
@login_required
def receipt():
   return  render_template('payment_receipt.html',now=datetime.now())
import os, json
from flask import current_app
# ------------routes for giving advice ------------
from flask import render_template, request, flash, redirect, url_for

@app.route('/give_advice/<int:patient_id>', methods=['GET', 'POST'])
def give_advice(patient_id):
    patient = Patient.query.get_or_404(patient_id)    
    # This block handles the form submission (POST request)
    if request.method == 'POST':
        prescribed_drugs_str = request.form.get('prescribed_drugs')        
        prescribed_drug_names = [name.strip() for name in prescribed_drugs_str.split(',') if name.strip()]        
        # Find the Drug objects in the database
        prescribed_drugs = Drug.query.filter(Drug.name.in_(prescribed_drug_names)).all()        
        new_advice = Advice( patient=patient)        
        for drug in prescribed_drugs:
            new_advice.prescribed_drugs.append(drug)            
        try:
            db.session.add(new_advice)
            db.session.commit()
            flash("Advice saved successfully!", 'success')
            return redirect(url_for('patient_profile', patient_id=patient.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", 'danger')
            return redirect(url_for('give_advice', patient_id=patient.id))          
    # This block handles displaying the page (GET request)
    available_drugs = Drug.query.all()
    return render_template('give_advice.html', patient=patient, available_drugs=available_drugs)

@app.route("/api/drugs")
def get_drugs():
    # Query the database to get all drug entries
    all_drugs = Drug.query.all()
    
    # Convert the list of SQLAlchemy objects to a list of dictionaries
    # This makes them easily convertible to JSON.
    drugs_list = [
        {"name": drug.name}
        for drug in all_drugs
    ]
    
    # Return the list as a JSON response
    return jsonify(drugs_list)
@app.route("/advice/history/<int:patient_id>")
@login_required
def advice_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    advices = Advice.query.filter_by(patient_id=patient.id).order_by(Advice.timestamp.desc()).all()
    return render_template("advice_history.html", patient=patient, advices=advices)

# --- DOCX Generation Logic ---
# New route for the patient data entry form
@app.route('/patient_data_entry', methods=['GET'])
def data_entry_form():
    now=date.today()
    available_drugs = Drug.query.all()
    return render_template('patient_form.html', patient_id=1001, available_drugs=available_drugs,today=now)

# New Route to export as  Docx file --
@app.route('/create_patient_doc/<int:patient_id>')
def create_patient_doc(patient_id):
    # Fetch patient data using the ID from the URL
    patient = Patient.query.options(joinedload(Patient.advice).joinedload(Advice.prescribed_drugs)).get_or_404(patient_id)   
    # Get doctor data from the currently logged-in user
    doctor_data = {
        'name': current_user.username,
        'specialization': current_user.degree,
        'reg_no': current_user.reg_no,
        'doc_mob':current_user.doc_mob,
        'website':current_user.website,
    }
    doc = Document()
    section= doc.sections[0]
    section.top_margin= Cm(1.0)
    # Recommended: Also set other margins for consistency
    section.bottom_margin = Cm(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    # --- Doctor and Document Header Section ---
    header_table = doc.add_table(rows=1, cols=2)
    header_table.style = 'Table Grid'
    header_table.autofit = True  
    format_table_header(header_table, bg="0070C0", text=(255, 255, 255))
    # Left cell for Doctor Info
    doctor_cell1 = header_table.cell(0, 0)
    #right cell for other info
    docCell2= header_table.cell(0,1)

    #doctor_cell1.width = Cm(10) # Set a fixed width
   # set_cell_background(doctor_cell1,"4F81BD")
   # set_cell_background(docCell2,"92CDDC")
   # set_cell_text(doctor_cell1, "", (255, 255, 255))
    #set_cell_text_color(doctor_cell1, (255, 255, 255)) 
    doctor_para = doctor_cell1.paragraphs[0]
    dp1= doctor_para.add_run(doctor_data['name'])
    dp1.font.size= Pt(22)
    dp1.bold==True
    dp1.font.name='Times New Roman'
    doctor_para.add_run(f"\n{doctor_data.get('specialization', '')}")
    doctor_para.add_run(f"\nReg. No: {doctor_data.get('reg_no', '')}")
    # Right cell for date & website
    date_cell = header_table.cell(0, 1)
    date_cell.width = Cm(8) # Set a fixed width
    right_para = date_cell.paragraphs[0]
    right_para.add_run(f"\n{doctor_data.get('website', '')}")
    right_para.add_run(f"\nMobile:{doctor_data.get('doc_mob','')}" )
    right_para.add_run(f"\nDate: {datetime.now().strftime('%d-%m-%Y')}")
    detailPara= doc.add_heading('')
    detailPara.add_run('')
    run_underlined = detailPara.add_run('Patient details')
    run_underlined.underline =True
    detailPara.alignment = WD_ALIGN_PARAGRAPH.CENTER
    #doc.add_heading('patient details') ==WD_ALIGN_PARAGRAPH.CENTER
 # --- Patient Details Section ---
    p_details = doc.add_paragraph()
    p_details.add_run('Name: ').bold = True
    p_details.add_run( patient.name).bold = True
    p_details.add_run(' | Age: ')
    p_details.add_run(str(patient.age)).bold = True
    p_details.add_run(' | Gender: ')
    p_details.add_run(patient.gender).bold = True  
    p_details.add_run(' | Address: ')
    p_details.add_run(patient.address).bold = True
    
    # --- Main Content Section (Two-Column Layout) ---
    content_table = doc.add_table(rows=1, cols=2)
    content_table.autofit = False
    content_table.style = 'Table Grid'
    
    # Left Column: Vitals and Complaints
    vitals_cell = content_table.cell(0, 0)
    vitals_cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    vitals_cell.width = Cm(6)
   
    vitals_cell.add_paragraph('Vitals & Complaints')
    
    # Since your patient model doesn't have these fields, we'll use placeholders
    vitals_cell.paragraphs[0].add_run('\nChief Complaint: ')
    vitals_cell.paragraphs[0].add_run('N/A').bold = True

    vitals_cell.paragraphs[0].add_run('\nTemp.: ')
    vitals_cell.paragraphs[0].add_run('N/A').bold = True
    
    vitals_cell.paragraphs[0].add_run('\nBP: ').bold=True
    vitals_cell.paragraphs[0].add_run('N/A').bold = True
    
    vitals_cell.paragraphs[0].add_run('\nPulse: ')
    vitals_cell.paragraphs[0].add_run('N/A').bold = True
   
    # Right Column: Advice
    advice_cell = content_table.cell(0, 1)
    advice_cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    advice_cell.width = Cm(12)
    advice_cell.add_paragraph('Advice')
    
    # Add advice from your patient advice records
    if patient.advice:
        for advice in patient.advice:
            #advice_cell.paragraphs[0].add_run(f"Advice on {advice.timestamp.strftime('%Y-%m-%d')}:\n").bold = True
            if advice.prescribed_drugs:
                for drug in advice.prescribed_drugs:
                    advice_cell.add_paragraph(f"{drug.name} " ,style='List Bullet')
    else:
        advice_cell.paragraphs[0].add_run("No advice recorded.")   
    doc.add_paragraph().add_run().add_break()   
    #doc.add_paragraph().add_run().add_break()   
    # --- Doctor's Signature ---
    signature_path = os.path.join(current_app.root_path, 'static', 'signature.png')
     # 3. Check if the signature file exists before adding it
    if os.path.exists(signature_path):
        # Add the picture to the document
        # Set a reasonable width (e.g., 1.5 inches or 3.8 cm) to avoid distortion
        doc.add_picture(signature_path, width=Inches(1))
        image_para= doc.paragraphs[-1]
        image_para.alignment= WD_ALIGN_PARAGRAPH.LEFT
        image_para.paragraph_format.space_after= Pt(0)
        image_para.paragraph_format.line_spacing = 1
           
    else:
        # Placeholder line if signature is missing, also with minimal spacing
        placeholder_para = doc.add_paragraph('_________________________')
        placeholder_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        placeholder_para.paragraph_format.space_after = Pt(0)
    # 3. Add the doctor's name beneath the signature/line
    doctor_brac = f"({doctor_data['name']})"
    p_name = doc.add_paragraph(doctor_brac)
    today=datetime.now().strftime('%d-%m-%Y')
    p_date=doc.add_paragraph(today)
    p_date.alignment=WD_ALIGN_PARAGRAPH.LEFT
    p_date.paragraph_format.space_before=Pt(0)
    p_date.paragraph_format.line_spacing =1

    # Set space before the paragraph containing the name to zero (0 points)
    p_name.paragraph_format.space_before = Pt(0)
    p_name.paragraph_format.line_spacing = 1
    
     # Save the document to a buffer instead of a file
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)    
    # Send the file to the user for download
    filename = f'{patient.name} Advice.docx'
    return send_file(doc_io, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

# ---------------------------
# Run and creates all tables if they don’t exist
if __name__ == "__main__":
 with app.app_context():
    db.create_all()
    app.run(debug=True, port=5050)
