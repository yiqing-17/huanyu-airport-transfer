from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(16))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///huanyu.db').replace('postgres://','postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False)
    service_type = db.Column(db.String(20), nullable=False)
    airport = db.Column(db.String(50), nullable=False)
    area = db.Column(db.String(150), nullable=False)
    vehicle = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    passengers = db.Column(db.Integer, nullable=False)
    luggage = db.Column(db.Integer, default=0)
    address = db.Column(db.Text, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    flight = db.Column(db.String(30), default='')
    note = db.Column(db.Text, default='')
    price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='待確認')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

PRICES = {
'國產五人座轎車': [
('台北市｜萬華、中正、大安、信義、大同、中山、松山',1000,1100),('台北市｜內湖、士林、北投、文山、南港',1100,1200),('新北市｜林口、鶯歌',900,1000),('新北市｜泰山、三峽、新莊、五股、三重、蘆洲',1000,1100),('新北市｜樹林、八里、板橋、土城、中和、永和',1000,1100),('新北市｜汐止、新店、淡水',1200,1300),('新北市｜深坑、石碇',1600,1700),('新北市｜瑞芳、坪林、三芝',1600,1700),('新北市｜烏來、雙溪、平溪',1900,2000),('新北市｜貢寮、石門、金山、萬里',2300,2400),('基隆市',1400,1500),('桃園市｜桃園、龜山、中壢、平鎮、蘆竹、新屋、觀音、八德',900,1000),('桃園市｜楊梅、龍潭、大溪、復興',1000,1100),('新竹區域｜新豐、湖口、竹北',1400,1500),('新竹區域｜新埔、關西、芎林、橫山、竹東、寶山、峨眉、北埔',1700,1800),('苗栗區域｜竹南、頭份',2200,2300),('苗栗區域｜其餘苗栗區域',2400,2500),('台中',2600,2700),('彰化',3500,3600),('南投',4000,4100),('宜蘭區域｜頭城、礁溪、宜蘭、壯圍、員山',2800,2900),('宜蘭區域｜羅東、五結、三星、冬山',2800,2900),('宜蘭區域｜蘇澳、大同、南澳',3000,3100),('花蓮',6500,6600),('台東',10500,10600),('嘉義',5000,5100),('台南',6000,6100),('高雄',6500,6600),('屏東',7000,7100)],
'國產五人座休旅車': [
('台北市｜萬華、中正、大安、信義、大同、中山、松山',1200,1300),('台北市｜內湖、士林、北投、文山、南港',1200,1300),('新北市｜林口、鶯歌',1100,1200),('新北市｜泰山、三峽、新莊、五股、三重、蘆洲',1200,1300),('新北市｜樹林、八里、板橋、土城、中和、永和',1200,1300),('新北市｜汐止、新店、淡水',1600,1800),('新北市｜深坑、石碇',1900,2000),('新北市｜瑞芳、坪林、三芝',1900,2000),('新北市｜烏來、雙溪、平溪',2100,2200),('新北市｜貢寮、石門、金山、萬里',2500,2600),('基隆市',1700,1800),('桃園市｜桃園、龜山、中壢、平鎮、蘆竹、新屋、觀音、八德',1100,1200),('桃園市｜楊梅、龍潭、大溪、復興',1200,1300),('新竹區域｜新豐、湖口、竹北',1700,1800),('新竹區域｜新埔、關西、芎林、橫山、竹東、寶山、峨眉、北埔',2000,2100),('苗栗區域｜竹南、頭份',2400,2500),('苗栗區域｜其餘苗栗區域',2600,2700),('台中',2800,2900),('彰化',3700,3800),('南投',4200,4300),('宜蘭區域｜頭城、礁溪、宜蘭、壯圍、員山',3000,3100),('宜蘭區域｜羅東、五結、三星、冬山',3000,3100),('宜蘭區域｜蘇澳、大同、南澳',3200,3300),('花蓮',7200,7300),('台東',10700,10800),('嘉義',5200,5300),('台南',6200,6300),('高雄',6700,6800),('屏東',7200,7300)],
'國產九人座商務車': [
('台北市｜萬華、中正、大安、信義、大同、中山、松山',1600,1700),('台北市｜內湖、士林、北投、文山、南港',1700,1800),('新北市｜林口、鶯歌',1600,1700),('新北市｜泰山、三峽、新莊、五股、三重、蘆洲',1600,1700),('新北市｜樹林、八里、板橋、土城、中和、永和',1600,1700),('新北市｜汐止、新店、淡水',1900,2000),('新北市｜深坑、石碇',2000,2200),('新北市｜瑞芳、坪林、三芝',1900,2000),('新北市｜烏來、雙溪、平溪',2400,2500),('新北市｜貢寮、石門、金山、萬里',2600,2700),('基隆市',1800,1900),('桃園市｜桃園、龜山、中壢、平鎮、蘆竹、新屋、觀音、八德',1300,1400),('桃園市｜楊梅、龍潭、大溪、復興',1600,1700),('新竹區域｜新豐、湖口、竹北',1900,2000),('新竹區域｜新埔、關西、芎林、橫山、竹東、寶山、峨眉、北埔',2100,2200),('苗栗區域｜竹南、頭份',2500,2600),('苗栗區域｜其餘苗栗區域',2700,2800),('台中',2900,3000),('彰化',4000,4100),('南投',4500,4600),('宜蘭區域｜頭城、礁溪、宜蘭、壯圍、員山',3300,3400),('宜蘭區域｜羅東、五結、三星、冬山',3300,3400),('宜蘭區域｜蘇澳、大同、南澳',3500,3600),('花蓮',7500,7600),('台東',11500,11600),('嘉義',5500,5600),('台南',6300,6400),('高雄',7000,7100),('屏東',8000,8100)],
'進口賓士九人座': [
('台北市｜萬華、中正、大安、信義、大同、中山、松山',1800,1900),('台北市｜內湖、士林、北投、文山、南港',1900,2000),('新北市｜林口、鶯歌',1900,2000),('新北市｜泰山、三峽、新莊、五股、三重、蘆洲',1900,2000),('新北市｜樹林、八里、板橋、土城、中和、永和',2200,2300),('新北市｜汐止、新店、淡水',2200,2300),('新北市｜深坑、石碇',2000,2200),('新北市｜瑞芳、坪林、三芝',2600,2700),('新北市｜烏來、雙溪、平溪',2700,2800),('新北市｜貢寮、石門、金山、萬里',3100,3200),('基隆市',2000,2100),('桃園市｜桃園、龜山、中壢、平鎮、蘆竹、新屋、觀音、八德',1600,1700),('桃園市｜楊梅、龍潭、大溪、復興',1900,2000),('新竹區域｜新豐、湖口、竹北',2100,2200),('新竹區域｜新埔、關西、芎林、橫山、竹東、寶山、峨眉、北埔',2400,2500),('苗栗區域｜竹南、頭份',2600,2700),('苗栗區域｜其餘苗栗區域',2800,2900),('台中',3300,3400),('彰化',4300,4400),('南投',5000,5100),('宜蘭區域｜頭城、礁溪、宜蘭、壯圍、員山',3800,3900),('宜蘭區域｜羅東、五結、三星、冬山',3800,3900),('宜蘭區域｜蘇澳、大同、南澳',4000,4100),('花蓮',8000,8100),('台東',12000,12100),('嘉義',6000,6100),('台南',6500,6600),('高雄',7500,7600),('屏東',9000,9100)]}

@app.route('/')
def home():
    return render_template('index.html', prices=PRICES, vehicle_names=list(PRICES))

@app.get('/api/quote')
def quote():
    vehicle=request.args.get('vehicle'); area=request.args.get('area'); service=request.args.get('service','pickup')
    try:
        rows=PRICES[vehicle]; row=next(r for r in rows if r[0]==area)
        return jsonify(ok=True, price=row[1 if service=='pickup' else 2])
    except Exception:
        return jsonify(ok=False, message='找不到對應價格'),400

@app.post('/api/bookings')
def create_booking():
    data=request.get_json() or {}
    required=['service_type','airport','area','vehicle','date','time','passengers','address','name','phone']
    if any(not str(data.get(k,'')).strip() for k in required):
        return jsonify(ok=False,message='請完整填寫必填資料'),400
    try:
        rows=PRICES[data['vehicle']]; row=next(r for r in rows if r[0]==data['area'])
        price=row[1 if data['service_type']=='pickup' else 2]
        order='HY'+datetime.now().strftime('%Y%m%d%H%M%S')+secrets.token_hex(2).upper()
        b=Booking(order_no=order, service_type=data['service_type'], airport=data['airport'], area=data['area'], vehicle=data['vehicle'], date=data['date'], time=data['time'], passengers=int(data['passengers']), luggage=int(data.get('luggage',0)), address=data['address'], name=data['name'], phone=data['phone'], flight=data.get('flight',''), note=data.get('note',''), price=price)
        db.session.add(b); db.session.commit()
        return jsonify(ok=True, order_no=order, price=price)
    except Exception as e:
        db.session.rollback(); return jsonify(ok=False,message=str(e)),500

@app.get('/admin')
def admin():
    bookings=Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin.html', bookings=bookings)

@app.post('/admin/<int:booking_id>/status')
def update_status(booking_id):
    b=Booking.query.get_or_404(booking_id); b.status=request.form.get('status','待確認'); db.session.commit(); return ('',204)

with app.app_context(): db.create_all()

if __name__=='__main__': app.run(debug=True, host='127.0.0.1', port=5000)
