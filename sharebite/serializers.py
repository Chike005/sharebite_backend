""" Serailizers """
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Donation, Proof, DropOffsite, Receipt, DropoffLocation

class UserSerializer(serializers.ModelSerializer):
    """ User serialize"""
    class Meta:
        """ meta """
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'password', \
                  'email', 'is_donor', 'is_receiver']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_password(self, value):
        validate_password(value, self.instance or User(username=self.initial_data.get('username', ''), email=self.initial_data.get('email', '')))
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])
        return instance

    def create(self, validated_data):
        """ Create user """
        # Hash the password before saving
        password = validated_data.pop('password', None)
        is_donor = validated_data.pop('is_donor', False)
        is_receiver = validated_data.pop('is_receiver', False)

        user = User(**validated_data)
        if password:
            user.set_password(password)  # Properly hashes the password
        user.is_donor = is_donor
        user.is_receiver = is_receiver
        user.save()
        return user
class LimitedUserSerializer(serializers.ModelSerializer):
    """Small user details included in donation records."""
    class Meta:
        """ Needed field """
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']

class PublicUserSerializer(serializers.ModelSerializer):
    """Expose only a donor's display name on receiver browse results."""
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name']

class ProofSerializer(serializers.ModelSerializer):
    """ Proof Serializer """
    class Meta:
        """ meta """
        model = Proof
        fields = ['id', 'donation', 'proof_image', 'uploaded_by']
        read_only_fields = ['donation', 'uploaded_by']

class ReceiptSerializer(serializers.ModelSerializer):
    """ Receipt seerialize """
    class Meta:
        """ meta """
        model = Receipt
        fields = ['id', 'user', 'donation', 'proof_image', 'pickup_date', 'created_at']
        read_only_fields = ['user', 'donation']
class LReceiptSerializer(serializers.ModelSerializer):
    """ Receipt seerialize """
    class Meta:
        """ meta """
        model = Receipt
        fields = ['id', 'proof_image', 'pickup_date', 'created_at']

class CollectionPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = DropoffLocation
        fields = [
            'id', 'name', 'address', 'latitude', 'longitude', 'opening_hours',
            'accepted_food_types', 'instructions',
        ]

class DonationSerializer(serializers.ModelSerializer):
    """ Donation serialize """
    proof = ProofSerializer(read_only=True)
    donor = LimitedUserSerializer(read_only=True)
    reserved_by = LimitedUserSerializer(read_only=True)
    receipt = LReceiptSerializer(read_only=True)
    food_image = serializers.ImageField(
        required=False,
        allow_null=True,
        max_length=255,
    )
    collection_point = serializers.PrimaryKeyRelatedField(
        queryset=DropoffLocation.objects.all(),
    )
    collection_point_details = CollectionPointSerializer(
        source='collection_point',
        read_only=True,
    )

    def validate_food_image(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError('Food photos must be 5 MB or smaller.')

            name, extension = value.name.rsplit('.', 1) if '.' in value.name else (value.name, '')
            extension = f'.{extension}' if extension else ''
            maximum_name_length = 90
            if len(value.name) > maximum_name_length:
                available_stem_length = maximum_name_length - len(extension)
                value.name = f'{name[:available_stem_length]}{extension}'
        return value

    class Meta:
        """ meta """
        model = Donation
        fields = ['id','donor', 'receipt', 'title', 'description', 'food_image',\
                   'quantity', 'expiry_date',\
                   'location', 'is_reserved', 'is_delivered', 'created_at', \
                    'reserved_by', 'proof', 'status', 'collection_point', \
                    'collection_point_details', 'collection_status']

        read_only_fields = [
            'is_reserved', 'is_delivered', 'status', 'reserved_by',
            'collection_status',
        ]

    def get_proof(self, obj):
        """ GET FULL URL """
        request = self.context.get('request')
        if obj.proof:
            return request.build_absolute_uri(obj.proof.url)
        return None

    def get_receipt(self, obj):
        """ GET FULL URL """
        request = self.context.get('request')
        if obj.receipt:
            return request.build_absolute_uri(obj.receipt.url)
        return None

class AvailableDonationSerializer(serializers.ModelSerializer):
    """Donation fields receivers need to assess an available collection-point donation."""
    donor = PublicUserSerializer(read_only=True)
    collection_point_details = CollectionPointSerializer(
        source='collection_point',
        read_only=True,
    )

    class Meta:
        model = Donation
        fields = [
            'id', 'donor', 'title', 'description', 'food_image', 'quantity',
            'expiry_date', 'location', 'is_reserved', 'is_delivered',
            'created_at', 'status', 'collection_point', 'collection_point_details',
            'collection_status',
        ]

class DropOffSiteSerializer(serializers.ModelSerializer):
    """ Drop Serializer """
    added_by = UserSerializer(read_only=True)
    class Meta:
        """ meta """
        model = DropOffsite
        fields = ['id', 'location', 'added_by', 'created_at']
