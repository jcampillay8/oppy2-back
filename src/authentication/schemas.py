# src/authentication/schemas.py

from pydantic import UUID4, BaseModel, EmailStr, Field, field_validator, model_validator
from pydantic_core.core_schema import FieldValidationInfo
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from src.config import settings


class UserPublicSchema(BaseModel):
    """
    Esquema público para la información del usuario, usado para respuestas de API.
    Consolida la información del perfil y la respuesta de login.
    """
    id: int
    user_guid: UUID4 = Field(..., alias="guid") 

    username: str
    email: EmailStr
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    user_image: Optional[str] = Field(None, alias="userImage")
    settings: Dict[str, Any] = Field({})
    has_accepted_terms: bool = Field(..., alias="termsAccepted")

    token_expires_at: Optional[int] = Field(
        None, 
        alias="tokenExpiresAt", 
    )

    class Config:
        from_attributes = True
        populate_by_name = True

    @model_validator(mode='before')
    @classmethod
    def inject_default_tour_flag(cls, data: Any) -> Any:
        if hasattr(data, 'settings'):
            current_settings = (data.settings or {}).copy()
            if 'show_tour' not in current_settings:
                current_settings['show_tour'] = True
            
            # Si es un objeto de SQLAlchemy
            if hasattr(data, '__dict__'):
                return {**data.__dict__, "settings": current_settings}
        return data
    # -------------------------------------------------------------

    @field_validator("user_image")
    # ... (resto de la función field_validator, sin cambios)
    @classmethod
    def add_image_host(cls, image_url: str | None) -> str | None:
        if image_url:
            if "/static/" in image_url and settings.ENVIRONMENT == "development":
                return settings.STATIC_HOST + image_url
        return image_url


class ForgotPasswordSchema(BaseModel):
    # ... (el resto del archivo es el mismo)
    email: EmailStr = Field(..., description="Email address of the user requesting password reset.")

class ResetPasswordSchema(BaseModel):
    # ... (el resto del archivo es el mismo)
    token: str = Field(..., min_length=1, description="Password reset token received via email.")
    new_password: str = Field(..., min_length=6, max_length=128, description="New password for the user.")
    confirm_password: str = Field(..., min_length=6, max_length=128, description="Confirmation of the new password.")

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info: FieldValidationInfo) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Las contraseñas no coinciden.")
        return v
    
class LoginResponseSchema(UserPublicSchema):
    """
    Esquema de respuesta para el endpoint /login.
    Incluye los datos públicos del usuario + tokens.
    """
    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field("bearer", alias="tokenType")