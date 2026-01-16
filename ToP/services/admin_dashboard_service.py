# ToP/services/admin_dashboard_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from django.apps import apps
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.forms import ModelForm
from django.forms import modelform_factory
from django.http import Http404
from django.shortcuts import get_object_or_404

from ..utils.admin_dashboard_utils import (
    ModelDashboardConfig,
    build_search_q,
    get_all_top_models,
    get_model_config,
    safe_model_count,
)


@dataclass(frozen=True)
class ModelListResult:
    model_name: str
    model_verbose_name: str
    model_verbose_name_plural: str
    fields: List[str]
    page_obj: Any
    query: str
    all_models: List[str]
    can_create: bool


@dataclass(frozen=True)
class ModelFormResult:
    model_name: str
    model_verbose_name: str
    action: str
    form: ModelForm
    all_models: List[str]


@dataclass(frozen=True)
class ModelDeleteResult:
    model_name: str
    model_verbose_name: str
    obj: models.Model
    all_models: List[str]


class AdminDashboardService:
    """
    Service for:
    - dashboard home data
    - model list with search + pagination
    - create/update forms
    - delete flow
    Preserves the existing behavior/logic.
    """

    def __init__(self, app_label: str = "ToP", page_size: int = 20):
        self.app_label = app_label
        self.page_size = page_size

    # ------------------------------
    # Home
    # ------------------------------
    def build_home_context(self) -> Dict[str, Any]:
        all_models = list(apps.get_app_config(self.app_label).get_models())
        models_data: List[Dict[str, Any]] = []

        for model in all_models:
            models_data.append({
                "name": model._meta.model_name,
                "verbose_name": model._meta.verbose_name,
                "verbose_name_plural": model._meta.verbose_name_plural,
                "count": safe_model_count(model),
            })

        models_data.sort(key=lambda x: x["verbose_name_plural"])

        return {
            "models_data": models_data,
            "all_models": [m._meta.model_name for m in all_models],
        }

    # ------------------------------
    # Resolve model + config
    # ------------------------------
    def resolve_model_or_404(self, model_name: str) -> ModelDashboardConfig:
        model, config = get_model_config(self.app_label, model_name)
        if not model or not config:
            raise Http404(f"Model {model_name} not found")
        return config

    # ------------------------------
    # Listing with search + pagination
    # ------------------------------
    def list_model_objects(self, *, model_name: str, query: str, page_number: Optional[str]) -> ModelListResult:
        config = self.resolve_model_or_404(model_name)
        model = config.model

        objects = model.objects.all().order_by("pk")

        if query:
            q_obj = build_search_q(model, query, config.search_fields)
            objects = objects.filter(q_obj)

        paginator = Paginator(objects, self.page_size)
        page_obj = paginator.get_page(page_number)

        return ModelListResult(
            model_name=model_name,
            model_verbose_name=model._meta.verbose_name,
            model_verbose_name_plural=model._meta.verbose_name_plural,
            fields=config.list_display,
            page_obj=page_obj,
            query=query,
            all_models=get_all_top_models(self.app_label),
            can_create=config.can_create,
        )

    # ------------------------------
    # Forms
    # ------------------------------
    def build_form_class(self, config: ModelDashboardConfig) -> Type[ModelForm]:
        return modelform_factory(config.model, fields="__all__", exclude=config.exclude_fields)

    def create_instance(self, *, model_name: str, post_data, files) -> Dict[str, Any]:
        """
        Returns dict with:
        - ok: bool
        - form: ModelForm
        - config: ModelDashboardConfig
        - instance: model instance (if ok)
        """
        config = self.resolve_model_or_404(model_name)

        if not config.can_create:
            return {"ok": False, "blocked": True, "config": config, "form": None, "instance": None}

        FormClass = self.build_form_class(config)
        form = FormClass(post_data, files)

        if form.is_valid():
            instance = form.save(commit=False)
            instance.save()
            return {"ok": True, "blocked": False, "config": config, "form": form, "instance": instance}

        return {"ok": False, "blocked": False, "config": config, "form": form, "instance": None}

    def get_create_form(self, *, model_name: str) -> ModelFormResult:
        config = self.resolve_model_or_404(model_name)
        FormClass = self.build_form_class(config)
        return ModelFormResult(
            model_name=model_name,
            model_verbose_name=config.model._meta.verbose_name,
            action="Create",
            form=FormClass(),
            all_models=get_all_top_models(self.app_label),
        )

    def update_instance(self, *, model_name: str, pk: int, post_data, files) -> Dict[str, Any]:
        config = self.resolve_model_or_404(model_name)
        obj = get_object_or_404(config.model, pk=pk)

        FormClass = self.build_form_class(config)
        form = FormClass(post_data, files, instance=obj)

        if form.is_valid():
            instance = form.save()
            return {"ok": True, "config": config, "form": form, "instance": instance, "obj": obj}

        return {"ok": False, "config": config, "form": form, "instance": None, "obj": obj}

    def get_update_form(self, *, model_name: str, pk: int) -> ModelFormResult:
        config = self.resolve_model_or_404(model_name)
        obj = get_object_or_404(config.model, pk=pk)

        FormClass = self.build_form_class(config)
        return ModelFormResult(
            model_name=model_name,
            model_verbose_name=config.model._meta.verbose_name,
            action="Update",
            form=FormClass(instance=obj),
            all_models=get_all_top_models(self.app_label),
        )

    # ------------------------------
    # Delete
    # ------------------------------
    def can_delete(self, *, model_name: str) -> bool:
        config = self.resolve_model_or_404(model_name)
        return bool(config.can_delete)

    def delete_instance(self, *, model_name: str, pk: int) -> models.Model:
        config = self.resolve_model_or_404(model_name)
        obj = get_object_or_404(config.model, pk=pk)
        obj.delete()
        return obj

    def get_delete_context(self, *, model_name: str, pk: int) -> ModelDeleteResult:
        config = self.resolve_model_or_404(model_name)
        obj = get_object_or_404(config.model, pk=pk)
        return ModelDeleteResult(
            model_name=model_name,
            model_verbose_name=config.model._meta.verbose_name,
            obj=obj,
            all_models=get_all_top_models(self.app_label),
        )
