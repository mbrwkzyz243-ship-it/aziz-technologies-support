import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
app=Flask(__name__)
app.config.update(SECRET_KEY=os.getenv('SECRET_KEY','local-dev-only-change-before-deploy'), SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL','sqlite:///support.db').replace('postgres://','postgresql://',1), SQLALCHEMY_TRACK_MODIFICATIONS=False, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower()=='true')
db=SQLAlchemy(app); login=LoginManager(app); login.login_view='login'; CSRFProtect(app)
class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),nullable=False); email=db.Column(db.String(180),unique=True,nullable=False,index=True); password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(20),default='student',nullable=False)
 def set_password(self,p): self.password_hash=generate_password_hash(p)
 def check_password(self,p): return check_password_hash(self.password_hash,p)
class Ticket(db.Model):
 id=db.Column(db.Integer,primary_key=True); title=db.Column(db.String(150),nullable=False); category=db.Column(db.String(50),nullable=False); details=db.Column(db.Text,nullable=False); location=db.Column(db.String(150)); status=db.Column(db.String(30),default='جديد',nullable=False); created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); owner=db.relationship('User',backref='tickets')
@login.user_loader
def load_user(uid): return db.session.get(User,int(uid))
class Register(FlaskForm):
 name=StringField('الاسم',validators=[DataRequired(),Length(min=2,max=100)]); email=StringField('البريد الإلكتروني',validators=[DataRequired(),Email(),Length(max=180)]); password=PasswordField('كلمة المرور (12 حرفًا على الأقل)',validators=[DataRequired(),Length(min=12,max=128)]); confirm=PasswordField('تأكيد كلمة المرور',validators=[DataRequired(),EqualTo('password')]); submit=SubmitField('إنشاء الحساب')
class Login(FlaskForm):
 email=StringField('البريد الإلكتروني',validators=[DataRequired(),Email()]); password=PasswordField('كلمة المرور',validators=[DataRequired()]); submit=SubmitField('دخول')
class NewTicket(FlaskForm):
 title=StringField('عنوان الطلب',validators=[DataRequired(),Length(min=4,max=150)]); category=SelectField('نوع الطلب',choices=[('صيانة جهاز','صيانة جهاز'),('مشكلة شبكة','مشكلة شبكة'),('برامج','برامج'),('حساب أو صلاحيات','حساب أو صلاحيات'),('أخرى','أخرى')]); location=StringField('الموقع أو القاعة (اختياري)',validators=[Length(max=150)]); details=TextAreaField('تفاصيل المشكلة',validators=[DataRequired(),Length(min=10,max=4000)]); submit=SubmitField('إرسال الطلب')
class Status(FlaskForm):
 status=SelectField('الحالة',choices=[('جديد','جديد'),('قيد المعالجة','قيد المعالجة'),('بانتظار معلومات','بانتظار معلومات'),('تم الحل','تم الحل')]); submit=SubmitField('حفظ الحالة')
@app.context_processor
def inject(): return {'year':datetime.utcnow().year}
@app.route('/')
def home(): return redirect(url_for('tickets')) if current_user.is_authenticated else render_template('home.html')
@app.route('/register',methods=['GET','POST'])
def register():
 if current_user.is_authenticated:return redirect(url_for('tickets'))
 f=Register()
 if f.validate_on_submit():
  email=f.email.data.strip().lower()
  if User.query.filter_by(email=email).first(): flash('هذا البريد مسجل مسبقًا.','error')
  else:
   u=User(name=f.name.data.strip(),email=email,role='student');u.set_password(f.password.data);db.session.add(u);db.session.commit();flash('تم إنشاء الحساب، سجّل الدخول.','success');return redirect(url_for('login'))
 return render_template('register.html',form=f)
@app.route('/login',methods=['GET','POST'])
def login_view():
 if current_user.is_authenticated:return redirect(url_for('tickets'))
 f=Login()
 if f.validate_on_submit():
  u=User.query.filter_by(email=f.email.data.strip().lower()).first()
  if u and u.check_password(f.password.data):login_user(u);return redirect(url_for('tickets'))
  flash('بيانات الدخول غير صحيحة.','error')
 return render_template('login.html',form=f)
@app.route('/logout',methods=['POST'])
@login_required
def logout():logout_user();return redirect(url_for('home'))
@app.route('/tickets')
@login_required
def tickets():
 rows=Ticket.query.order_by(Ticket.created_at.desc()).all() if current_user.role=='engineer' else Ticket.query.filter_by(user_id=current_user.id).order_by(Ticket.created_at.desc()).all()
 return render_template('tickets.html',tickets=rows)
@app.route('/tickets/new',methods=['GET','POST'])
@login_required
def new_ticket():
 f=NewTicket()
 if f.validate_on_submit():
  t=Ticket(title=f.title.data.strip(),category=f.category.data,details=f.details.data.strip(),location=(f.location.data or '').strip(),user_id=current_user.id);db.session.add(t);db.session.commit();flash('تم إرسال الطلب.','success');return redirect(url_for('tickets'))
 return render_template('new_ticket.html',form=f)
@app.route('/tickets/<int:tid>',methods=['GET','POST'])
@login_required
def detail(tid):
 t=db.session.get(Ticket,tid)
 if t is None:abort(404)
 if current_user.role!='engineer' and t.user_id!=current_user.id:abort(403)
 f=Status()
 if current_user.role=='engineer':
  if f.validate_on_submit():t.status=f.status.data;db.session.commit();flash('تم تحديث الحالة.','success');return redirect(url_for('detail',tid=t.id))
  f.status.data=t.status
 return render_template('detail.html',ticket=t,form=f)
@app.errorhandler(403)
def forbidden(e):return render_template('error.html',code=403,message='ليس لديك صلاحية لعرض هذا الطلب.'),403
@app.errorhandler(404)
def missing(e):return render_template('error.html',code=404,message='الصفحة أو الطلب غير موجود.'),404
with app.app_context():
 db.create_all(); email=os.getenv('ENGINEER_EMAIL','').strip().lower(); password=os.getenv('ENGINEER_PASSWORD','')
 if email and password and len(password)>=16 and not User.query.filter_by(email=email).first():
  u=User(name='المهندس المسؤول',email=email,role='engineer');u.set_password(password);db.session.add(u);db.session.commit()
if __name__=='__main__':app.run()
