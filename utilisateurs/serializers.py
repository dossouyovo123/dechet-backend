from django.core.mail import send_mail
from django.conf import settings
from .models import CustomUser,SacCitoyen,PlanificationCollecte,Notification,Retrait
from rest_framework import serializers
from .login_serializers import LoginSerializer
from django.utils import timezone

class CitizenRegistrationSerializer(serializers.ModelSerializer):
    passwordConfirmation = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password', 'passwordConfirmation')
        extra_kwargs = {
            'password': {'write_only': True, 'style': {'input_type': 'password'}},
            'email': {'required': True},
        }

    def validate(self, data):
        if data['password'] != data['passwordConfirmation']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        return data

    def generate_formatted_id(self):
        last_user = CustomUser.objects.order_by('-id').first()
        next_id = 1 if not last_user else last_user.id + 1
        return f"C/{next_id:04d}"

    def create(self, validated_data):
        validated_data.pop('passwordConfirmation')

        # Créer l'utilisateur sans id_formatte pour l'instant
        user = CustomUser(
            username=validated_data['username'],
            email=validated_data['email']
        )
        user.set_password(validated_data['password'])
        user.save()  # L'ID est maintenant généré 

        # Générer et enregistrer l'identifiant formaté
        user.id_formatte = f"C/{user.id:04d}"
        user.save()

        # Envoyer l'email
        subject = 'Votre identifiant formaté'
        message = (
            f'Bonjour {user.username},\n\n'
            f'Voici votre identifiant  de connexion : {user.id_formatte}\n\n'
            'Merci de vous être inscrit.'
        )
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=True,
        )

        return user

class CollectorRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [ 'id','username', 'email', 'adresse']
       

    def validate_email(self, value):
        """
        Vérifie si l'e-mail est unique lors de la création,
        ou s'il est modifié pour un utilisateur existant.
        """
        # Si c'est une mise à jour (self.instance existe) et que l'email n'a pas changé,
        # on passe la validation sans vérifier l'unicité.
        if self.instance and self.instance.email == value:
            return value

        # Sinon (nouvel utilisateur ou email modifié), vérifie l'unicité.
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un utilisateur avec cet e-mail existe déjà.")
        return value

  
    def validate_username(self, value):
        return value

    def update(self, instance, validated_data):
        """
        Met à jour et retourne une instance CustomUser existante,
        étant donné les données de validation.
        Cette méthode est appelée par ModelViewSet pour les requêtes PUT/PATCH.
        """
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.adresse = validated_data.get('adresse', instance.adresse)


        instance.save()
        return instance




class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'id_formatte', 'username', 'email', 'adresse'] 


class SacCitoyenSerializer(serializers.ModelSerializer):
    citoyen = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.filter(user_type='citoyen'))
    adresse = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = SacCitoyen
        fields = ['id', 'citoyen', 'sac_vert', 'sac_noir', 'sac_jaune', 'date_reception', 'adresse'] 
        read_only_fields = ['date_reception']

        
    def get_date_reception(self, obj):
        # Format : Jour/Mois/Année Heure:Minute
        return obj.date_reception.strftime('%d/%m/%Y %H:%M')


from .models import Collecte
from django.contrib.auth import get_user_model
User = get_user_model()


from .models import Collecte, SacCitoyen  

User = get_user_model()
User = get_user_model()
User = get_user_model()

class CollecteSerializer(serializers.ModelSerializer):
    citoyen_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_type='citoyen'),
        source='citoyen',
        write_only=True,
        label='ID du citoyen'
    )
    collecteur_id = serializers.PrimaryKeyRelatedField(
        source='collecteur',
        read_only=True,
        label='ID du collecteur'
    )
    nom_citoyen = serializers.CharField(source='citoyen.username', read_only=True)
    nom_collecteur = serializers.CharField(source='collecteur.username', read_only=True)
    adresse = serializers.SerializerMethodField()

    class Meta:
        model = Collecte
        fields = [
            'id',
            'citoyen_id',
            'collecteur_id',
            'nom_citoyen',
            'nom_collecteur',
            'adresse',
            'date_collecte',
            'point_vert',
            'point_jaune',
            'point_noir',
            'statut',
            'total_collectes_collecteur_citoyen', # Nouveau nom de champ
        ]
        read_only_fields = ['id', 'nom_citoyen', 'nom_collecteur', 'date_collecte', 'adresse', 'total_collectes_collecteur_citoyen'] # Nouveau nom de champ

    def get_adresse(self, obj):
        try:
            sac_citoyen = SacCitoyen.objects.get(citoyen=obj.citoyen)
            return sac_citoyen.adresse
        except SacCitoyen.DoesNotExist:
            return 'N/A'

    def create(self, validated_data):
        validated_data['collecteur'] = self.context['request'].user
      
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.point_vert = validated_data.get('point_vert', instance.point_vert)
        instance.point_jaune = validated_data.get('point_jaune', instance.point_jaune)
        instance.point_noir = validated_data.get('point_noir', instance.point_noir)
        instance.date_collecte = validated_data.get('date_collecte', instance.date_collecte)
        instance.statut = validated_data.get('statut', instance.statut)
        
        instance.save()
        return instance
    
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'adresse', 'user_type']  




#planification de collecte serializers
class PlanificationCollecteSerializer(serializers.ModelSerializer):
   
    collecteurs_assignes = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        many=True # Indique que c'est une relation Many-to-Many
    )

    class Meta:
        model = PlanificationCollecte
        fields = ['id', 'ville', 'quartier', 'date_collecte', 'heure_collecte', 'collecteurs_assignes']

class NotificationSerializer(serializers.ModelSerializer):
    recipient = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())

    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'message', 'created_at', 'is_read', 'latitude', 'longitude']
        read_only_fields = ['created_at'] 



from rest_framework import serializers
from django.db.models import Sum
from decimal import Decimal
from django.contrib.auth import get_user_model 

User = get_user_model()
from .models import Retrait, Collecte
class RetraitCollecteurSerializer(serializers.ModelSerializer):
    # Ce champ est pour l'entrée (client) et map vers 'montant' du modèle
    montant_demande = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        source='montant',
        write_only=True
    )
    collecteur_nom_complet = serializers.SerializerMethodField(read_only=True)
    traite_par_nom_complet = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Retrait
        fields = [
            'id', 'collecteur', 'collecteur_nom_complet', 'nom_beneficiaire',
            'prenom_beneficiaire', 'numero_beneficiaire', 'montant_demande',
            'statut', 'date_demande', 'date_traitement', 'traite_par', 'traite_par_nom_complet',
            'transaction_id_fournisseur', 'message_echec', 'montant' # 'montant' pour la sortie
        ]
        read_only_fields = [
            'id', 'collecteur', 'collecteur_nom_complet', 'statut', 'date_demande',
            'date_traitement', 'traite_par', 'traite_par_nom_complet',
            'transaction_id_fournisseur', 'message_echec'
        ]

    def get_collecteur_nom_complet(self, obj):
        return obj.collecteur.get_full_name() if obj.collecteur else "N/A"

    def get_traite_par_nom_complet(self, obj):
        return obj.traite_par.get_full_name() if obj.traite_par else "N/A"

    def validate(self, data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentification requise pour effectuer un retrait.")

        collecteur_demandeur = request.user
        if collecteur_demandeur.user_type != 'collector':
            raise serializers.ValidationError("Seuls les collecteurs peuvent utiliser cette méthode de retrait.")

        montant_retrait = data.get('montant') # Accès au montant via le champ modèle

        if montant_retrait is None or montant_retrait <= 0:
            raise serializers.ValidationError("Le montant demandé doit être un nombre positif.")

        TARIF_PAR_COLLECTE = Decimal('100') # Définissez votre tarif fixe ici

        # Calculer les gains théoriques du collecteur
        total_collectes_count = Collecte.objects.filter(collecteur=collecteur_demandeur).count()
        gains_theoriques = Decimal(total_collectes_count) * TARIF_PAR_COLLECTE

        # Calculer le total des montants déjà retirés (approuvés ou en attente)
        total_retraits_effectues = Retrait.objects.filter(
            collecteur=collecteur_demandeur,
            statut__in=['approuve', 'en_attente']
        ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.00')

        gains_actuels_disponibles = gains_theoriques - total_retraits_effectues

        if montant_retrait > gains_actuels_disponibles:
            raise serializers.ValidationError(
                {'montant_demande': f'Solde insuffisant. Gains disponibles: {gains_actuels_disponibles} CFA.'}
            )

        data['collecteur'] = collecteur_demandeur # Assigner l'utilisateur authentifié
        data['statut'] = 'en_attente'
        return data

    def create(self, validated_data):
        return Retrait.objects.create(**validated_data)

class RetraitCitoyenSerializer(serializers.ModelSerializer):
    # Les champs pour l'entrée Flutter
    nom_beneficiaire = serializers.CharField(max_length=100)
    prenom_beneficiaire = serializers.CharField(max_length=100, allow_null=True, allow_blank=True)
    numero_beneficiaire = serializers.CharField(max_length=20)
    montant_demande = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        source='montant', # Ceci mappe 'montant_demande' du front au champ 'montant' du modèle Retrait
        write_only=True # Ce champ est pour l'entrée, pas pour la sortie
    )

    class Meta:
        model = Retrait
        fields = [
            'nom_beneficiaire', 'prenom_beneficiaire', 'numero_beneficiaire',
            'montant_demande',
        ]
        # Ne pas inclure 'citoyen' ou 'collecteur' ici, car ils sont assignés dans la vue.

    def validate(self, data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentification requise pour effectuer un retrait.")

        citoyen_demandeur = request.user
        if not hasattr(citoyen_demandeur, 'user_type') or citoyen_demandeur.user_type != 'citoyen':
            raise serializers.ValidationError({"detail": "Seuls les citoyens peuvent demander un retrait via cette méthode."})

        # Accès au montant via le champ 'montant' du modèle, qui est mappé depuis 'montant_demande'
        montant_retrait = data.get('montant') 
        
        if montant_retrait is None or montant_retrait <= 0:
            raise serializers.ValidationError({"montant_demande": "Le montant demandé doit être un nombre positif."})

        TAUX_CONVERSION_POINT_CFA = Decimal('0.16')

        # --- CORRECTION ICI : Somme des points par type de sac comme sur votre frontend ---
        # Le filtre pour Collecte utilise 'citoyen=citoyen_demandeur', ce qui est correct si Collecte a un champ 'citoyen'.
        collectes_citoyen = Collecte.objects.filter(citoyen=citoyen_demandeur)
        
        total_points_vert = collectes_citoyen.aggregate(Sum('point_vert'))['point_vert__sum'] or 0
        total_points_jaune = collectes_citoyen.aggregate(Sum('point_jaune'))['point_jaune__sum'] or 0
        total_points_noir = collectes_citoyen.aggregate(Sum('point_noir'))['point_noir__sum'] or 0

        total_points_accumules = total_points_vert + total_points_jaune + total_points_noir
        # --- FIN DE LA CORRECTION ---

        gains_theoriques_cfa = Decimal(total_points_accumules) * TAUX_CONVERSION_POINT_CFA

        # IMPORTANT : Filtrez les retraits existants par le nouveau champ 'citoyen' du modèle Retrait
        total_retraits_citoyen = Retrait.objects.filter(
            citoyen=citoyen_demandeur, # <--- MODIFICATION CLÉ ICI : Utilisez le champ 'citoyen'
            statut__in=['approuve', 'en_attente', 'complete_kkiapay']
        ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.00')

        solde_actuel_disponible = gains_theoriques_cfa - total_retraits_citoyen

        if montant_retrait > solde_actuel_disponible:
            raise serializers.ValidationError(
                {'montant_demande': f'Solde insuffisant. Votre solde disponible est de {solde_actuel_disponible.quantize(Decimal("0.01"))} CFA.'}
            )

        return data

    def create(self, validated_data):
        # La vue est responsable d'assigner 'citoyen', 'collecteur', 'statut' etc.
        # Ici, le serializer se contente de créer l'instance de Retrait avec les données validées.
        return Retrait.objects.create(**validated_data)
