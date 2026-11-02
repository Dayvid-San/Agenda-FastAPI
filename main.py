from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status

# Garante que os dados da aplicação tenham os formatos corretos
from pydantic import BaseModel, EmailStr, Field, field_validator

# ORM (Object-Relational Mapping)
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# --- Configuração do Banco de Dados (SQLite local) ---
DATABASE_URL = "sqlite:///./agenda.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- Modelo do Banco (SQLAlchemy) ---
class ContactModel(Base):
    # O __tablename__ está indicando que esta classe está vinculada a tabela contacts
    # Assim, ele puxa os campos das tabelas no banco de dados
    __tablename__ = "contacts"

    # Assim, podemos trabalhar com os bancos aqui assim
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Esse é o comando que realmente cria as tabelas no banco de dados
Base.metadata.create_all(bind=engine)


# --- Dependência de Sessão ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Schemas de Validação (Pydantic) ---
class ContactBase(BaseModel):
    # min_length=1 impede strings vazias ""
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=8, max_length=20)
    # EmailStr valida o formato sintático do e-mail
    email: Optional[EmailStr] = None

    @field_validator("name", "phone", mode="before")
    @classmethod
    def strip_and_validate_not_empty(cls, value: any) -> any:
        # Se vier null/None, deixa o Pydantic disparar o erro nativo de tipo
        if value is None:
            return value

        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("field cannot be empty or contain only whitespaces")
            return cleaned

        return value

class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=8, max_length=20)
    email: Optional[EmailStr] = None

    @field_validator("name", "phone", mode="before")
    @classmethod
    def validate_optional_fields(cls, value: any) -> any:
        if value is None:
            raise ValueError("field cannot be null")

        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("field cannot be empty or contain only whitespaces")
            return cleaned

        return value


class ContactResponse(ContactBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
 

# --- Aplicação FastAPI ---
app = FastAPI(title="Agenda API", version="1.0.0")


@app.post(
    "/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED
)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    
    new_contact = ContactModel(**contact.model_dump())
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact


@app.get("/contacts", response_model=List[ContactResponse])
def list_contacts(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(ContactModel).offset(skip).limit(limit).all()


@app.get("/contacts/{contact_id}", response_model=ContactResponse)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(ContactModel).filter(ContactModel.id == contact_id).first()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with id {contact_id} not found",
        )
    return contact


@app.put("/contacts/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int, contact_update: ContactUpdate, db: Session = Depends(get_db)
):
    contact = db.query(ContactModel).filter(ContactModel.id == contact_id).first()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with id {contact_id} not found",
        )

    update_data = contact_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)
    return contact


@app.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(ContactModel).filter(ContactModel.id == contact_id).first()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with id {contact_id} not found",
        )

    db.delete(contact)
    db.commit()
    return None
