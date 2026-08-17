"""
Seeds the database with demo users and properties so you can run the
app and immediately see it working — useful for your project demo/viva.

Run: python seed.py
"""
from app import create_app
from app.models import db, User, Property, PropertyImage, Review

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()

    admin = User(name="Admin User", email="admin@estate.com", role="admin", phone="9900000000")
    admin.set_password("admin123")

    agent1 = User(name="Ramesh Kumar", email="agent1@estate.com", role="agent", phone="9900000001")
    agent1.set_password("agent123")

    agent2 = User(name="Priya Sharma", email="agent2@estate.com", role="agent", phone="9900000002")
    agent2.set_password("agent123")

    customer = User(name="Devaraj M S", email="customer@estate.com", role="customer", phone="9900000003")
    customer.set_password("customer123")

    db.session.add_all([admin, agent1, agent2, customer])
    db.session.commit()

    demo_properties = [
        dict(title="Sunrise Apartments 2BHK", description="Well-ventilated 2BHK near tech park, close to metro.",
             property_type="Apartment", listing_type="Rent", price=25000, city="Bengaluru",
             locality="Whitefield", bedrooms=2, bathrooms=2, area_sqft=1100,
             agent_id=agent1.id, status="approved"),
        dict(title="Green Meadows Villa", description="Independent 4BHK villa with garden and parking.",
             property_type="Villa", listing_type="Sale", price=9500000, city="Bengaluru",
             locality="Sarjapur Road", bedrooms=4, bathrooms=4, area_sqft=2800,
             agent_id=agent1.id, status="approved"),
        dict(title="Commercial Office Space", description="Prime commercial space, ready to move in.",
             property_type="Commercial", listing_type="Rent", price=60000, city="Bengaluru",
             locality="Koramangala", bedrooms=0, bathrooms=2, area_sqft=1800,
             agent_id=agent2.id, status="approved"),
        dict(title="Lakeview Residency 3BHK", description="Spacious 3BHK with lake view and clubhouse access.",
             property_type="Apartment", listing_type="Sale", price=7800000, city="Bengaluru",
             locality="Hebbal", bedrooms=3, bathrooms=3, area_sqft=1650,
             agent_id=agent2.id, status="pending"),
    ]

    props = []
    for data in demo_properties:
        p = Property(**data)
        db.session.add(p)
        props.append(p)
    db.session.flush()

    placeholder_images = [
        "https://placehold.co/600x400?text=Property+Photo+1",
        "https://placehold.co/600x400?text=Property+Photo+2",
    ]
    for p in props:
        for url in placeholder_images:
            db.session.add(PropertyImage(property_id=p.id, image_url=url))

    db.session.add(Review(property_id=props[0].id, customer_id=customer.id,
                           rating=5, comment="Great location, very responsive agent."))
    db.session.add(Review(property_id=props[1].id, customer_id=customer.id,
                           rating=4, comment="Beautiful villa, slightly above my budget but worth it."))

    db.session.commit()

    print("Seed complete.")
    print("Login credentials:")
    print("  Admin:    admin@estate.com / admin123")
    print("  Agent:    agent1@estate.com / agent123")
    print("  Customer: customer@estate.com / customer123")
