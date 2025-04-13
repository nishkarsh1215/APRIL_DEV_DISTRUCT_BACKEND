import datetime
from mongoengine import (
    Document,
    IntField,
    StringField,
    BooleanField,
    DateTimeField,
    ListField,
    ReferenceField,
    CASCADE
)

# Define EditorMessage first so it is available for references.
class EditorMessage(Document):
    prompt = StringField(required=True)
    response = StringField()
    created_at = DateTimeField(default=datetime.datetime.now(datetime.timezone.utc))
    
    meta = {"collection": "editor_messages"}
    
    def __str__(self):
        return f"EditorMessage({self.id}, Prompt: {self.prompt[:20]}...)"

class ChatMessage(Document):
    prompt = StringField(required=True)
    response = StringField()
    likes = IntField(default=0)
    dislikes = IntField(default=0)
    editor_message = ReferenceField('EditorMessage', reverse_delete_rule=CASCADE, null=True)
    created_at = DateTimeField(default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = DateTimeField(default=datetime.datetime.now(datetime.timezone.utc))
    
    meta = {"collection": "chat_messages"}
    
    def __str__(self):
        return f"ChatMessage({self.id}, Prompt: {self.prompt[:20]}...)"

class Chat(Document):
    title = StringField(required=True)
    chat_messages = ListField(ReferenceField('ChatMessage', reverse_delete_rule=CASCADE))
    editor_messages = ListField(ReferenceField('EditorMessage', reverse_delete_rule=CASCADE))
    created_at = DateTimeField(default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = DateTimeField(default=datetime.datetime.now(datetime.timezone.utc))
    
    meta = {"collection": "chats"}
    
    def __str__(self):
        return f"Chat({self.id}, {self.title})"

class User(Document):
    name = StringField(required=True, sparse=True)
    password = StringField()
    email = StringField(required=True, sparse=True)
    provider = StringField()
    githubId = StringField(default=None, sparse=True)
    googleId = StringField(default=None, sparse=True)
    emailVerified = BooleanField(default=False)
    freeCredits = IntField(default=1000)
    chatIds = ListField(ReferenceField('Chat', reverse_delete_rule=CASCADE))
    theme = StringField(default='light')
    created_at = DateTimeField(default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = DateTimeField(default=datetime.datetime.now(datetime.timezone.utc))
    
    meta = {
        "collection": "users",
        "indexes": ["email"]
    }
    
    def __str__(self):
        return f"User({self.id}, {self.name})"
