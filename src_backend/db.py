import code
from http.client import NETWORK_AUTHENTICATION_REQUIRED
from turtle import title
from unicodedata import name
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
import base64
import boto3
import datetime
import io
from io import BytesIO
from mimetypes import guess_extension, guess_type
import os
from PIL import Image
import random
import re
import string

db = SQLAlchemy()

EXTENSIONS = ["png", "gif", "jpg", "jpeg"]
BASE_DIR = os.getcwd()
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
S3_BASE_URL = f"https://{S3_BUCKET_NAME}.s3.us-east-1.amazonaws.com"

db = SQLAlchemy()

association_table = db.Table(
  "association",
  db.Column("post_id", db.Integer, db.ForeignKey("posts.id")),
  db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"))
)

class User(db.Model):
  """
  User Model

  One to Many relationship with Posts
  """
  __tablename__ = "users"
  id = db.Column(db.Integer, primary_key = True, autoincrement = True)
  username = db.Column(db.String, nullable=False)

  def __init__(self, **kwargs):
    """
    initialize user object
    """
    self.name = kwargs.get("name", "anonymous")

  def serialize(self):
    """
    serialize user object
    """ 
    return {
      "id" : self.id,
      "name" : self.name
    }


class Post(db.Model):
  """
  Post Model

  Many to One relationship with Users
  Many to One relationship with Location
  """
  __tablename__ = "posts"
  id = db.Column(db.Integer, primary_key = True, autoincrement = True)
  user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
  tags = db.Relationship("Tag", secondary=association_table, back_populates="posts")
  building = db.Column(db.String, nullable=False)
  latitude = db.Column(db.Integer, db.ForeignKey("locations.latitude"), nullable = False)
  longitude = db.Column(db.Integer, db.ForeignKey("locations.longitude"), nullable = False)
  img_url = db.Column(db.String, db.ForeignKey("assets.url"), nullable = False)
  room = db.Column(db.String)
  description = db.Column(db.String)
  image_URL = db.Column(db.String)

  def __init__(self, **kwargs):
    """
    initializes a post object
    """
    self.user_id = kwargs.get("user_id")
    self.building = kwargs.get("building", "")
    self.latitude = kwargs.get("latitude")
    self.longitude = kwargs.get("longitude")
    self.room = kwargs.get("room", "")
    self.image_URL = kwargs.get("url")
    self.description = kwargs.get("description", "")
    self.image_URL = kwargs.get("image_URL", "")

  def serialize(self):
    """
    Serialize Post object
    """
    return {
      "id" :self.id,
      "user_id" : self.user_id,
      "building" : self.building,
      "room" : self.room,
      "latitude" : self.latitude,
      "longitude" : self.longitude,
      "description" : self.description,
      "tags" : [t.simple_serialize() for t in self.tags],
      "image_URL" : self.image_URL,
    }


class Location(db.Model):
  """
  Location Model

  One to Many relationship with Posts
  """
  __tablename__ = "locations"
  id = db.Column(db.Integer, primary_key = True, autoincrement = True)
  name = db.Column(db.String, nullable = False)
  latitude = db.Column(db.Integer, nullable = False)
  longitude = db.Column(db.Integer, nullable = False)

  def __init__(self, **kwargs):
    """
    initialize location object
    """
    self.name = kwargs.get("name", "")
    self.latitude = kwargs.get("latitude")
    self.longitude = kwargs.get("longitude")

  def serialize(self):
    """
    serialize location object
    """
    return {
      "id" : self.id,
      "name" : self.name,
      "latitude" : self.latitude,
      "longitude" : self.longitude
    }

class Asset(db.Model):
  """
  Asset model
  """
  __tablename__ = "assets"
  id = db.Column(db.Integer, primary_key=True, autoincrement=True)
  base_url = db.Column(db.String, nullable=True)
  salt = db.Column(db.String, nullable=False)
  extension = db.Column(db.String, nullable=False)
  width = db.Column(db.Integer, nullable=False)
  height = db.Column(db.Integer, nullable=False)
  created_at = db.Column(db.DateTime, nullable=False)

  def __init__(self, **kwargs):
      """
      Initializes an Asset object
      """
      self.create(kwargs.get("image_data"))

  def serialize(self):
      """
      Serializes an Asset object
      """
      return {
          "url" :self.url(),
          "created_at" : str(self.created_at)
      }

  def create(self, image_data):
    """
    Given an image in base64 form, does the following:
    1. Rejects the image if it is not a support filetype
    2. Generates a random string for the image filename
    3. Decodes the image and attempts to upload it to AWS
    """
    try:
      ext = guess_extension(guess_type(image_data)[0])[1:]

      # only accept supported file extensions
      if ext not in EXTENSIONS:
        raise Exception(f"Unsupported file type: {ext}")

      # secure way of generating a random string for image filename
      salt = "".join(
          random.SystemRandom().choice(
              string.ascii_uppercase + string.digits
          )
          for _ in range(16)
      )

      # remove header of base64 string
      img_str = re.sub("^data:image/.+;base64,", "", image_data)
      img_data = base64.b64decode(img_str)
      img = Image.open(BytesIO(img_data))

      self.base_url = S3_BASE_URL
      self.salt = salt
      self.extension = ext
      self.width = img.width
      self.height = img.height
      self.created_at = datetime.datetime.now()

      img_filename = f"{self.salt}.{self.extension}"
      self.upload(img, img_filename)
      return f"{self.base_url}/{self.salt}.{self.extension}"
    
    except Exception as e:
      
      print(f"Error when creating image: {e}")


  def url(self):
    return f"{self.base_url}/{self.salt}.{self.extension}"

  def upload(self, img, img_filename):
      """
      Attempts to upload the image to the specified S3 bucket
      """
      try:
          # save image temporarily on server
          img_temploc = f"{BASE_DIR}/{img_filename}"
          img.save(img_temploc)

          # upload the image to S3
          s3_client = boto3.client("s3")
          s3_client.upload_file(img_temploc, S3_BUCKET_NAME, img_filename)

          # make S3 image url is public
          s3_resource = boto3.resource("s3")
          object_acl = s3_resource.ObjectAcl(S3_BUCKET_NAME, img_filename)
          object_acl.put(ACL="public-read")

          # remove image from server
          os.remove(img_temploc)

      except Exception as e:
          print(f"Error when uploading image: {e}")

class Tag(db.Model):
  """
  Tag model
  """
  __tablename__= "tags"
  id = db.Column(db.Integer, primary_key = True, autoincrement = True)
  allergen = db.Column(db.String, nullable = False)
  posts = db.relationship("Post", secondary=association_table, back_populates="tags")

  def __init__(self, **kwargs):
    """
    Initializes a Tag object
    """
    self.allergen = kwargs.get("allergen", "")

  def serialize(self):
    """
    Serializes a Tag object
    """
    return {
      "id" : self.id,
      "allergen" : self.allergen,
      "posts" : [p.simple_serialize() for p in self.posts]
    }

  def simple_serialize(self):
    """
    Serializes a Tag object
    """
    return {
      "id" : self.id,
      "allergen" : self.allergen
    }


    