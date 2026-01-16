from rest_framework import serializers
from .models import *

class UnitSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(write_only=True)

    class Meta:
        model = Unit
        exclude = ['company']

    def validate(self, data):
        # If serializer is used in PATCH mode, skip required fields validation
        if self.partial:
            return data

        # Normal validation for POST / PUT
        required_fields = [
            "unit_code",
            "development_delivery_date",
            "num_bedrooms",
            "finishing_specs",
            "sellable_area",
            "garden_area",
            "penthouse_area",
            "uncovered_terraces",
            "roof_terraces_area",
            "interest_free_unit_price",
        ]

        missing = [field for field in required_fields if data.get(field) is None]
        
        if missing:
            raise serializers.ValidationError(
                {field: "This field is required." for field in missing}
            )

        return data


    def create(self, validated_data):
        company_name = validated_data.pop("company_name")
        company = Company.objects.filter(name=company_name).first()
        if not company:
            raise serializers.ValidationError(f"Company '{company_name}' not found.")

        original_code = str(validated_data.get("unit_code"))
        full_code = f"{company_name}_{original_code}"

        validated_data["company"] = company
        validated_data["unit_code"] = full_code

        instance, _ = Unit.objects.update_or_create(
            unit_code=full_code,
            defaults=validated_data
        )
        return instance



from rest_framework import serializers
from .models import Company, Project, Unit

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'num_users', 'is_active', 'logo']

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name', 'description']

class UnitSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project_company.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Unit
        fields = [
            'unit_code', 'city', 'project_name', 'unit_type', 'area_range',
            'adj_status', 'sellable_area', 'psm', 'sales_value',
            'status', 'company_name'
        ]

