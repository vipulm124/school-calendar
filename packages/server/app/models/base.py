"""
This module defines the base class for all database models.

The `Base` class provides common functionality and structure for all models,
including shared columns and table naming conventions.
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import BOOLEAN, CHAR, TIMESTAMP, VARCHAR


class Base(DeclarativeBase):
    """
    Base class for all database models.

    This class includes shared attributes and functionality that are inherited
    by all other models in the application.
    """

    @declared_attr.directive
    def __tablename__(self: Any) -> str:
        """
        Automatically generates the table name for the model by converting
        the class name from CamelCase to snake_case.
        """
        table_name = re.sub("(?<!^)(?=[A-Z])", "_", self.__name__).lower()
        return table_name

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid4())
    )
    is_active: Mapped[bool] = mapped_column(BOOLEAN, default=True)
    is_deleted: Mapped[bool] = mapped_column(BOOLEAN, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=datetime.now,
    )
    created_by: Mapped[str] = mapped_column(VARCHAR(100))
    updated_by: Mapped[str] = mapped_column(VARCHAR(100))

    def __repr__(self) -> str:
        """
        Returns a string representation of the model instance.
        """
        column_data = ", ".join(
            f"{key}={value}"
            for key, value in self.__dict__.items()
            if not key.startswith("_")
        )
        return f"<{self.__class__.__name__}({column_data})>"

    def to_dict(self, *, dont_filter_audit: bool = False) -> Dict[str, Any]:
        """
        Converts the model instance into a dictionary, excluding audit columns.
        """
        audit_columns = {
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        }
        if dont_filter_audit:
            audit_columns = set()
        return {
            key: (
                value.value
                if isinstance(value, Enum)
                else (
                    value.isoformat()
                    if isinstance(value, datetime)
                    else str(value) if isinstance(value, str) else value
                )
            )
            for key, value in self.__dict__.items()
            if key not in audit_columns and not key.startswith("_")
        }
