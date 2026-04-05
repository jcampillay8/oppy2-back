# src/avatars/schemas.py
from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import humps
from .enums import OutputFormatEnum, VoiceKeyEnum


def to_camel(string: str) -> str:
    return humps.camelize(string)

# --- ESQUEMAS DE PERFIL ANFITRIÓN (HOST) ---

class OppyHostAvatarProfileOut(BaseModel):
    """
    Esquema de salida para un perfil de avatar anfitrión predefinido.
    """
    id: int
    name: str
    role_avatar: str = Field(alias="roleAvatar")
    role_usuario: str = Field(alias="roleUsuario")
    objective: str
    context: str
    character_traits: Optional[str] = Field(None, alias="characterTraits")
    rules: Optional[str] = Field(None)
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

# --- SCHEMAS DE AVATAR ---

class AvatarDefinitionBase(BaseModel):
    name: str = Field(..., max_length=150, description="Nombre descriptivo del avatar.")
    role_avatar: str = Field(..., max_length=500, description="El rol que desempeñará el avatar.")
    role_usuario: str = Field(..., max_length=255, description="El rol que el usuario tendrá.")
    objective: str = Field(..., max_length=500, description="El objetivo principal del avatar.")
    context: str = Field(..., description="El contexto general o escenario.")
    character_traits: Optional[str] = Field(None, description="Rasgos de carácter.")
    rules: Optional[str] = Field(None, description="Reglas específicas de comportamiento.")
    output_format_preference: Optional[OutputFormatEnum] = Field(OutputFormatEnum.NORMAL)
    language_preference: Optional[str] = Field("en-US", max_length=10)
    selected_voice: Optional[VoiceKeyEnum] = Field(VoiceKeyEnum.US_FEMALE)
    is_tts_enabled: bool = Field(False)
    is_public: Optional[bool] = Field(False)
    host_profile_id: Optional[int] = Field(None)

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class AvatarDefinitionCreate(AvatarDefinitionBase):
    pass

class AvatarDefinitionUpdate(BaseModel):
    """
    Esquema para actualizar una definición de avatar (campos opcionales).
    """
    name: Optional[str] = Field(None, max_length=150)
    role_avatar: Optional[str] = Field(None, max_length=500, alias="roleAvatar")
    role_usuario: Optional[str] = Field(None, max_length=255, alias="roleUsuario")
    objective: Optional[str] = Field(None, max_length=500)
    context: Optional[str] = Field(None)
    character_traits: Optional[str] = Field(None, alias="characterTraits")
    rules: Optional[str] = Field(None)
    output_format_preference: Optional[OutputFormatEnum] = Field(None)
    language_preference: Optional[str] = Field(None, max_length=10)
    selected_voice: Optional[VoiceKeyEnum] = Field(None)
    is_tts_enabled: Optional[bool] = Field(None)
    is_public: Optional[bool] = Field(None)
    host_profile_id: Optional[int] = Field(None)
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

class AvatarDefinitionOut(BaseModel):
    """
    Esquema de salida para la definición de un Avatar con lógica de herencia.
    """
    id: int
    guid: UUID
    user_id: int = Field(alias="userId")
    host_profile_id: Optional[int] = Field(None, alias="hostProfileId")
    name: str
    is_deleted: bool = Field(alias="isDeleted")
    is_public: bool = Field(alias="isPublic")

    # Estos campos se usan como respaldo si no hay host_profile
    role_avatar: Optional[str] = Field(None, alias="roleAvatar")
    role_usuario: Optional[str] = Field(None, alias="roleUsuario")
    objective: Optional[str] = Field(None)
    context: Optional[str] = Field(None)
    character_traits: Optional[str] = Field(None, alias="characterTraits")
    rules: Optional[str] = Field(None)

    host_profile: Optional[OppyHostAvatarProfileOut] = Field(None, exclude=True)

    @computed_field(alias="roleAvatar")
    @property
    def final_role_avatar(self) -> Optional[str]:
        if self.host_profile_id is not None and self.host_profile:
            return self.host_profile.role_avatar
        return self.role_avatar

    @computed_field(alias="roleUsuario")
    @property
    def final_role_usuario(self) -> Optional[str]:
        if self.host_profile_id is not None and self.host_profile:
            return self.host_profile.role_usuario
        return self.role_usuario

    @computed_field(alias="objective")
    @property
    def final_objective(self) -> Optional[str]:
        if self.host_profile_id is not None and self.host_profile:
            return self.host_profile.objective
        return self.objective

    @computed_field(alias="context")
    @property
    def final_context(self) -> Optional[str]:
        if self.host_profile_id is not None and self.host_profile:
            return self.host_profile.context
        return self.context

    @computed_field(alias="characterTraits")
    @property
    def final_character_traits(self) -> Optional[str]:
        if self.host_profile_id is not None and self.host_profile:
            return self.host_profile.character_traits
        return self.character_traits

    @computed_field(alias="rules")
    @property
    def final_rules(self) -> Optional[str]:
        if self.host_profile_id is not None and self.host_profile:
            return self.host_profile.rules
        return self.rules

    output_format_preference: Optional[OutputFormatEnum] = Field(None, alias="outputFormatPreference")
    language_preference: Optional[str] = Field(None, alias="languagePreference")
    selected_voice: Optional[VoiceKeyEnum] = Field(None, alias="selectedVoice")
    is_tts_enabled: Optional[bool] = Field(None, alias="isTtsEnabled")
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True, 
        from_attributes=True
    )

