from mongoengine import connect
import os
from dotenv import load_dotenv

load_dotenv()

def init_db():
    mongo_uri = os.getenv("MONGO_URI")
    connect(host=mongo_uri)
