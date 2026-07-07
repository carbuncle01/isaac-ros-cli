# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from collections.abc import Mapping
from pathlib import Path
from typing import Any, List, Optional, Type, TypeVar, Union

from pydantic import (
    BaseModel,
    constr,
    Extra,
    StrictBool,
    StrictInt,
    ValidationError,
    validator,
)

SUPPORTED_CONFIG_VERSION = 2


class InvalidConfigError(ValueError):
    """Raised when a config file or merged config violates the supported schema."""


NonEmptyString = constr(strict=True, min_length=1)


class _ConfigModel(BaseModel):
    class Config:
        extra = Extra.forbid


class DockerImageConfig(_ConfigModel):
    """Fully resolved Docker image config after all config layers have been merged."""

    base_image_keys: List[NonEmptyString]
    additional_image_keys: List[NonEmptyString]

    @validator("base_image_keys")
    def _validate_base_image_keys(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("must contain at least one value")
        return value


class DockerImageConfigOverlay(_ConfigModel):
    """Partial image-config patch from a single config source."""

    base_image_keys: Optional[List[NonEmptyString]] = None
    additional_image_keys: Optional[List[NonEmptyString]] = None

    @validator("base_image_keys")
    def _validate_base_image_keys(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is not None and not value:
            raise ValueError("must contain at least one value")
        return value


class DockerRunConfig(_ConfigModel):
    """Fully resolved Docker runtime config after all config layers have been merged."""

    container_name: NonEmptyString
    entrypoint: NonEmptyString
    workdir: NonEmptyString
    platform: NonEmptyString
    use_cached_build_image: StrictBool


class DockerRunConfigOverlay(_ConfigModel):
    """Partial runtime-config patch from a single config source."""

    container_name: Optional[NonEmptyString] = None
    entrypoint: Optional[NonEmptyString] = None
    workdir: Optional[NonEmptyString] = None
    platform: Optional[NonEmptyString] = None
    use_cached_build_image: Optional[StrictBool] = None


class DockerConfig(_ConfigModel):
    """Fully resolved Docker config subtree."""

    image: DockerImageConfig
    run: DockerRunConfig


class DockerConfigOverlay(_ConfigModel):
    """Partial Docker config patch from a single config source."""

    image: Optional[DockerImageConfigOverlay] = None
    run: Optional[DockerRunConfigOverlay] = None


class AptConfig(_ConfigModel):
    """Fully resolved Isaac ROS apt source config."""

    key_url: NonEmptyString
    repository: NonEmptyString
    distro: NonEmptyString
    components: List[NonEmptyString]

    @validator("components")
    def _validate_components(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("must contain at least one value")
        return value


class AptConfigOverlay(_ConfigModel):
    """Partial Isaac ROS apt source config patch from a single config source."""

    key_url: Optional[NonEmptyString] = None
    repository: Optional[NonEmptyString] = None
    distro: Optional[NonEmptyString] = None
    components: Optional[List[NonEmptyString]] = None

    @validator("components")
    def _validate_components(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is not None and not value:
            raise ValueError("must contain at least one value")
        return value


class IsaacRosCliConfig(_ConfigModel):
    """Complete Isaac ROS CLI config with every required field present."""

    version: StrictInt
    docker: DockerConfig
    apt: Optional[AptConfig] = None

    @validator("version")
    def _validate_version(cls, value: int) -> int:
        if value != SUPPORTED_CONFIG_VERSION:
            raise ValueError(f"must be set to {SUPPORTED_CONFIG_VERSION}")
        return value


class IsaacRosCliConfigOverlay(_ConfigModel):
    """Partial config layer that is legal to merge, but not necessarily complete on its own."""

    version: Optional[StrictInt] = None
    docker: Optional[DockerConfigOverlay] = None
    apt: Optional[AptConfigOverlay] = None

    @validator("version")
    def _validate_version(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value != SUPPORTED_CONFIG_VERSION:
            raise ValueError(f"must be set to {SUPPORTED_CONFIG_VERSION}")
        return value


def validate_config(config: Mapping[str, Any]) -> IsaacRosCliConfig:
    """Validate a fully merged Isaac ROS CLI config and return a complete model."""
    return _validate_model(
        IsaacRosCliConfig,
        config,
        source="Merged Isaac ROS CLI configuration",
    )


def validate_config_overlay(
    overlay: Mapping[str, Any],
    source: Union[str, Path],
) -> IsaacRosCliConfigOverlay:
    """Validate one partial config layer against the supported schema.

    Overlays intentionally allow missing keys because a single config file may only override a
    small subset of the final schema.
    """
    return _validate_model(
        IsaacRosCliConfigOverlay,
        overlay,
        source=str(source),
    )


ModelT = TypeVar("ModelT", bound=BaseModel)


def _validate_model(model_type: Type[ModelT], value: Mapping[str, Any], source: str) -> ModelT:
    try:
        return model_type.parse_obj(value)
    except ValidationError as exc:
        raise InvalidConfigError(_format_validation_error(source, exc)) from exc


def _format_validation_error(source: str, exc: ValidationError) -> str:
    error = exc.errors()[0]
    path = ".".join(["config", *(str(item) for item in error.get("loc", ()))])
    error_type = str(error.get("type", ""))
    message = str(error.get("msg", "invalid configuration")).rstrip(".")

    if error_type == "value_error.extra":
        return f"{source}: Unknown configuration key '{path}'."
    if error_type == "value_error.missing":
        return f"{source}: Missing required configuration key '{path}'."
    return f"{source}: '{path}' {message}."
