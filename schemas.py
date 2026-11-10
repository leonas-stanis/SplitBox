from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime


class ReadingBase(BaseModel):
    sensor: str = Field(min_length=1, max_length=20)
    content: float


class ReadingCreate(ReadingBase):
    user_id: int #Temporary


class ReadingUpdate(BaseModel):
    sensor: str | None = Field(default=None, min_length=1, max_length=20)
    content: float | None = Field(default=None)


class UserBase(BaseModel):
    username:str = Field(min_length=3, max_length=20)
    email: EmailStr = Field(max_length=320)


class UserCreate(UserBase):
    pass 

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_file: str | None
    image_path: str


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=20)
    email: EmailStr | None = Field(default=None, max_length=320)
    image_file: str | None = Field(default=None, max_length=200)


class ReadingResponse(ReadingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    date_timestamp: datetime
    author: UserResponse