from rest_framework import serializers
from apps.repositories.models import Repository
from apps.repositories.services import generate_webhook_secret


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = (
            'id', 'name', 'owner', 'full_name',
            'github_url', 'is_active', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'full_name', 'created_at', 'updated_at')

    def validate(self, attrs):
        attrs['full_name'] = f"{attrs['owner']}/{attrs['name']}"
        return attrs

    def create(self, validated_data):
        plain_secret, encrypted = generate_webhook_secret()
        validated_data['webhook_secret'] = encrypted
        # Store plain secret in context so view can show it once
        instance = super().create(validated_data)
        instance._plain_secret = plain_secret
        return instance


class RepositorySecretSerializer(serializers.ModelSerializer):
    webhook_secret = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = ('id', 'full_name', 'webhook_secret')

    def get_webhook_secret(self, obj):
        return self.context.get('plain_secret', '*** hidden ***')