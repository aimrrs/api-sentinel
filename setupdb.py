from database import engine, Base
import models

print("[ API - Sentinel ] Connecting to the database and creating tables...")

Base.metadata.create_all(bind=engine)

print("[ API - Sentinel ] Database tables created successfully!")
