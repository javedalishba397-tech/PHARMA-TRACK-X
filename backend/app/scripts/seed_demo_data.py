from datetime import date, datetime, timedelta
from decimal import Decimal
import random

from backend.app.db.session import SessionLocal, init_db
from backend.app.models.entities import (
    User, Medicine, Batch, Supplier, Customer, PurchaseOrder, PurchaseOrderItem, Sale, SaleItem, SystemSetting
)
from backend.app.core.security import get_password_hash
from backend.app.services.settings_service import init_system_settings
from backend.app.services.medicine_service import update_batch_statuses
from backend.app.services.recommendation_service import run_all_recommendations
from backend.app.services.supplier_service import update_supplier_observed_lead_time

def seed_data():
    init_db()
    db = SessionLocal()
    init_system_settings(db)

    print("Seeding initial data for PharmaTrack-X...")

    # 1. Users
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(
            full_name="Dr. Farhan Malik (Admin)",
            username="admin",
            password_hash=get_password_hash("Admin123!"),
            role="Administrator",
            email="admin@pharmatrackx.pk",
            is_active=True,
        )
        db.add(admin)

    pharmacist = db.query(User).filter(User.username == "pharmacist").first()
    if not pharmacist:
        pharmacist = User(
            full_name="Sabika Abbas (Pharmacist)",
            username="pharmacist",
            password_hash=get_password_hash("Pharma123!"),
            role="Pharmacist",
            email="pharmacist@pharmatrackx.pk",
            is_active=True,
        )
        db.add(pharmacist)

    clerk = db.query(User).filter(User.username == "clerk").first()
    if not clerk:
        clerk = User(
            full_name="Alishba Javed (Cashier)",
            username="clerk",
            password_hash=get_password_hash("Clerk123!"),
            role="Sales Clerk",
            email="clerk@pharmatrackx.pk",
            is_active=True,
        )
        db.add(clerk)

    db.commit()
    pharmacist = db.query(User).filter(User.username == "pharmacist").first()
    clerk = db.query(User).filter(User.username == "clerk").first()

    # 2. Suppliers
    suppliers_data = [
        {"name": "Getz Pharma Distribution", "contact_person": "Tariq Mehmood", "phone": "0300-1122334", "stated": 5},
        {"name": "GSK Consumer Healthcare Pakistan", "contact_person": "Kamran Khan", "phone": "0321-5566778", "stated": 4},
        {"name": "Searle Company Ltd", "contact_person": "Naveed Ahmed", "phone": "0333-9988776", "stated": 7},
        {"name": "Abbott Laboratories Pakistan", "contact_person": "Zahid Hussain", "phone": "0345-4433221", "stated": 6},
    ]
    sup_objs = []
    for s_data in suppliers_data:
        sup = db.query(Supplier).filter(Supplier.name == s_data["name"]).first()
        if not sup:
            sup = Supplier(
                name=s_data["name"],
                contact_person=s_data["contact_person"],
                phone=s_data["phone"],
                email=f"sales@{s_data['name'].lower().replace(' ', '')[:10]}.pk",
                address="Industrial Area, Korangi, Karachi",
                stated_lead_time_days=s_data["stated"],
                is_active=True,
            )
            db.add(sup)
            db.commit()
            db.refresh(sup)
        sup_objs.append(sup)

    # 3. Customers
    customers_data = [
        {"name": "Muhammad Usman", "phone": "0301-2345678", "address": "Gulshan-e-Iqbal, Block 5, Karachi"},
        {"name": "Fatima Zahra", "phone": "0322-9876543", "address": "PECHS Block 2, Karachi"},
        {"name": "Abdul Rehman", "phone": "0334-5544332", "address": "North Nazimabad, Karachi"},
    ]
    cust_objs = []
    for c_data in customers_data:
        c = db.query(Customer).filter(Customer.phone == c_data["phone"]).first()
        if not c:
            c = Customer(name=c_data["name"], phone=c_data["phone"], address=c_data["address"])
            db.add(c)
            db.commit()
            db.refresh(c)
        cust_objs.append(c)

    # 4. Medicines & Batches
    today = date.today()
    med_specs = [
        {
            "name": "Amoxicillin 500 mg",
            "generic_name": "Amoxicillin Trihydrate",
            "category": "Antibiotic",
            "dosage_form": "Capsule",
            "strength": "500 mg",
            "manufacturer": "Getz Pharma",
            "barcode": "8964000100112",
            "unit_price": Decimal("180.00"),
            "reorder_level": 50,
            "requires_prescription": True,
            "batches": [
                {"number": "B-2217", "expiry_days": 25, "qty": 120, "price": Decimal("120.00")}, # Figure 3.1 Prioritize!
                {"number": "B-2218", "expiry_days": 240, "qty": 150, "price": Decimal("120.00")},
            ],
            "sales_profile": "medium_steady",  # ~3 units/day -> ~90 units in 30 days
        },
        {
            "name": "Paracetamol 500 mg",
            "generic_name": "Paracetamol (Acetaminophen)",
            "category": "Analgesic / Antipyretic",
            "dosage_form": "Tablet",
            "strength": "500 mg",
            "manufacturer": "GSK Consumer Healthcare",
            "barcode": "8964000200223",
            "unit_price": Decimal("30.00"),
            "reorder_level": 100,
            "requires_prescription": False,
            "batches": [
                {"number": "B-3091", "expiry_days": 210, "qty": 40, "price": Decimal("18.00")}, # Figure 3.1 Reorder!
            ],
            "sales_profile": "high_demand", # ~7.5 units/day -> 225 units in 30 days. Stock 40 covers only 5 days < lead time 7!
        },
        {
            "name": "Insulin pen",
            "generic_name": "Insulin Glargine",
            "category": "Antidiabetic",
            "dosage_form": "Injection",
            "strength": "100 IU/ml",
            "manufacturer": "Abbott",
            "barcode": "8964000300334",
            "unit_price": Decimal("2400.00"),
            "reorder_level": 20,
            "requires_prescription": True,
            "batches": [
                {"number": "B-1188", "expiry_days": 60, "qty": 15, "price": Decimal("1800.00")}, # Figure 3.1 Review!
            ],
            "sales_profile": "erratic_low", # short/erratic -> Low confidence
        },
        {
            "name": "Cetirizine 10 mg",
            "generic_name": "Cetirizine Dihydrochloride",
            "category": "Antihistamine",
            "dosage_form": "Tablet",
            "strength": "10 mg",
            "manufacturer": "Searle Company Ltd",
            "barcode": "8964000400445",
            "unit_price": Decimal("75.00"),
            "reorder_level": 30,
            "requires_prescription": False,
            "batches": [
                {"number": "B-4001", "expiry_days": 365, "qty": 120, "price": Decimal("45.00")}, # Hold!
            ],
            "sales_profile": "low_steady", # 1.5 units/day -> 45 units in 30 days. Stock 120 covers 80 days.
        },
        {
            "name": "Augmentin 625 mg",
            "generic_name": "Co-Amoxiclav",
            "category": "Antibiotic",
            "dosage_form": "Tablet",
            "strength": "625 mg",
            "manufacturer": "GSK Consumer Healthcare",
            "barcode": "8964000500556",
            "unit_price": Decimal("320.00"),
            "reorder_level": 35,
            "requires_prescription": True,
            "batches": [
                {"number": "B-5001", "expiry_days": 180, "qty": 80, "price": Decimal("220.00")},
            ],
            "sales_profile": "medium_steady",
        },
        {
            "name": "Expired Test Medicine",
            "generic_name": "Expired Trial Substance",
            "category": "Testing",
            "dosage_form": "Tablet",
            "strength": "10 mg",
            "manufacturer": "Generic Labs",
            "barcode": "8964000999999",
            "unit_price": Decimal("50.00"),
            "reorder_level": 10,
            "requires_prescription": False,
            "batches": [
                {"number": "B-EXPIRED-99", "expiry_days": -15, "qty": 25, "price": Decimal("30.00")}, # Expired batch!
            ],
            "sales_profile": "zero",
        }
    ]

    for m_data in med_specs:
        med = db.query(Medicine).filter(Medicine.barcode == m_data["barcode"]).first()
        if not med:
            med = Medicine(
                name=m_data["name"],
                generic_name=m_data["generic_name"],
                category=m_data["category"],
                dosage_form=m_data["dosage_form"],
                strength=m_data["strength"],
                manufacturer=m_data["manufacturer"],
                barcode=m_data["barcode"],
                unit_price=m_data["unit_price"],
                reorder_level=m_data["reorder_level"],
                requires_prescription=m_data["requires_prescription"],
                is_active=True,
            )
            db.add(med)
            db.commit()
            db.refresh(med)

        for b_data in m_data["batches"]:
            b = db.query(Batch).filter(Batch.medicine_id == med.medicine_id, Batch.batch_number == b_data["number"]).first()
            if not b:
                exp_date = today + timedelta(days=b_data["expiry_days"])
                rec_date = today - timedelta(days=60)
                status = "Expired" if b_data["expiry_days"] < 0 else ("Near-Expiry" if b_data["expiry_days"] <= 90 else "Active")
                b = Batch(
                    medicine_id=med.medicine_id,
                    batch_number=b_data["number"],
                    expiry_date=exp_date,
                    received_date=rec_date,
                    qty_received=b_data["qty"] + 50,
                    qty_remaining=b_data["qty"],
                    purchase_price=b_data["price"],
                    status=status,
                    sell_first=False,
                )
                db.add(b)
                db.commit()

    # 5. Seed historical completed POs to create observed lead times
    if db.query(PurchaseOrder).count() == 0:
        for i, sup in enumerate(sup_objs):
            # Create 3 completed orders each
            for j in range(3):
                order_date = today - timedelta(days=90 - j * 20)
                lead = sup.stated_lead_time_days + (j % 2)  # realistic slight variance
                deliv_date = order_date + timedelta(days=lead)

                po = PurchaseOrder(
                    supplier_id=sup.supplier_id,
                    created_by=pharmacist.user_id,
                    order_date=order_date,
                    expected_delivery_date=order_date + timedelta(days=sup.stated_lead_time_days),
                    actual_delivery_date=deliv_date,
                    status="Received",
                    total_amount=Decimal("15000.00"),
                    notes=f"Historical delivery #{j+1}",
                )
                db.add(po)
                db.commit()
                db.refresh(po)

                # Add item
                item = PurchaseOrderItem(
                    po_id=po.po_id,
                    medicine_id=1,
                    qty_ordered=100,
                    qty_received=100,
                    unit_cost=Decimal("120.00"),
                )
                db.add(item)
                db.commit()

            update_supplier_observed_lead_time(db, sup.supplier_id)

    # 6. Seed 60 days of historical sales
    if db.query(Sale).count() == 0:
        print("Generating 60 days of historical sales records...")
        med_objs = db.query(Medicine).all()
        med_map = {m.name: m for m in med_objs}

        # Create temporary archive batches for past sales so current stock remains exact as desired
        for d in range(60, 0, -1):
            sale_date = datetime.combine(today - timedelta(days=d), datetime.min.time()) + timedelta(hours=14, minutes=random.randint(0, 50))
            
            # Sale for Amoxicillin (~3 units daily)
            amox = med_map.get("Amoxicillin 500 mg")
            if amox and amox.batches:
                b = amox.batches[0]
                qty = random.choice([2, 3, 3, 4, 3, 2, 4])
                s = Sale(
                    invoice_no=f"INV-HIST-{d:03d}-1",
                    customer_id=cust_objs[0].customer_id,
                    user_id=clerk.user_id,
                    sale_datetime=sale_date,
                    subtotal=amox.unit_price * qty,
                    discount_percent=Decimal("0.0"),
                    total_amount=amox.unit_price * qty,
                    status="Completed"
                )
                db.add(s)
                db.commit()
                db.refresh(s)
                si = SaleItem(sale_id=s.sale_id, batch_id=b.batch_id, quantity=qty, unit_price=amox.unit_price, line_total=amox.unit_price * qty)
                db.add(si)

            # Sale for Paracetamol (~7-8 units daily)
            para = med_map.get("Paracetamol 500 mg")
            if para and para.batches:
                b = para.batches[0]
                qty = random.choice([6, 7, 8, 7, 9, 7, 8])
                s = Sale(
                    invoice_no=f"INV-HIST-{d:03d}-2",
                    customer_id=cust_objs[1].customer_id,
                    user_id=clerk.user_id,
                    sale_datetime=sale_date + timedelta(minutes=15),
                    subtotal=para.unit_price * qty,
                    discount_percent=Decimal("0.0"),
                    total_amount=para.unit_price * qty,
                    status="Completed"
                )
                db.add(s)
                db.commit()
                db.refresh(s)
                si = SaleItem(sale_id=s.sale_id, batch_id=b.batch_id, quantity=qty, unit_price=para.unit_price, line_total=para.unit_price * qty)
                db.add(si)

            # Sale for Cetirizine (~2 units daily)
            cetz = med_map.get("Cetirizine 10 mg")
            if cetz and cetz.batches:
                b = cetz.batches[0]
                qty = random.choice([1, 2, 2, 2, 3, 1, 2])
                s = Sale(
                    invoice_no=f"INV-HIST-{d:03d}-3",
                    customer_id=None,
                    user_id=clerk.user_id,
                    sale_datetime=sale_date + timedelta(minutes=30),
                    subtotal=cetz.unit_price * qty,
                    discount_percent=Decimal("0.0"),
                    total_amount=cetz.unit_price * qty,
                    status="Completed"
                )
                db.add(s)
                db.commit()
                db.refresh(s)
                si = SaleItem(sale_id=s.sale_id, batch_id=b.batch_id, quantity=qty, unit_price=cetz.unit_price, line_total=cetz.unit_price * qty)
                db.add(si)

            # Insulin only had sales in the last 10 days, very erratic
            if d <= 10:
                ins = med_map.get("Insulin pen")
                if ins and ins.batches:
                    b = ins.batches[0]
                    qty = random.choice([0, 1, 0, 2, 0, 1])
                    if qty > 0:
                        s = Sale(
                            invoice_no=f"INV-HIST-{d:03d}-4",
                            customer_id=cust_objs[2].customer_id,
                            user_id=clerk.user_id,
                            sale_datetime=sale_date + timedelta(minutes=45),
                            subtotal=ins.unit_price * qty,
                            discount_percent=Decimal("0.0"),
                            total_amount=ins.unit_price * qty,
                            status="Completed"
                        )
                        db.add(s)
                        db.commit()
                        db.refresh(s)
                        si = SaleItem(sale_id=s.sale_id, batch_id=b.batch_id, quantity=qty, unit_price=ins.unit_price, line_total=ins.unit_price * qty)
                        db.add(si)

        db.commit()

    # 7. Run batch statuses & recommendations
    update_batch_statuses(db)
    print("Generating initial recommendations...")
    rec_count = run_all_recommendations(db)
    print(f"Generated {rec_count} initial recommendations.")

    db.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_data()
