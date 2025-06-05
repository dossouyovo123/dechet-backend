from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import CustomUser,SacCitoyen,Collecte,Notification,PlanificationCollecte
from .serializers import CitizenRegistrationSerializer,LoginSerializer,CollectorRegistrationSerializer,CustomUserSerializer
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework import generics, viewsets
from .models import PlanificationCollecte
from rest_framework.decorators import action
from .serializers import PlanificationCollecteSerializer,NotificationSerializer
from . import serializers
from django.contrib.auth import get_user_model
User = get_user_model()
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
import requests
import os
from django.conf import settings 
from .models import Retrait, CustomUser 
from .serializers import RetraitCollecteurSerializer, RetraitCitoyenSerializer 
from .models import Retrait
from django.contrib.auth import get_user_model 
import traceback
User = get_user_model()

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum # Assurez-vous que Sum est importé

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

from .models import Retrait, Collecte 
from .serializers import RetraitCollecteurSerializer, RetraitCitoyenSerializer 
from rest_framework.exceptions import ValidationError





#pour compter le nombre de planification

class PlanificationCountView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser] 

    def get(self, request, *args, **kwargs):
        total_planifications = PlanificationCollecte.objects.count()
        return Response({'total': total_planifications}, status=status.HTTP_200_OK)


# --- Vue pour la demande de retrait par un COLLECTEUR (avec Kkiapay) ---
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_withdrawal_collector(request):
    if request.user.user_type != 'collector':
        return Response(
            {'detail': 'Accès refusé. Seuls les collecteurs peuvent demander un retrait via cette méthode.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = RetraitCollecteurSerializer(data=request.data, context={'request': request})

    try:
        if serializer.is_valid(raise_exception=True):
            retrait = serializer.save(collecteur=request.user, statut='en_attente')

            # --- Démarrage de l'appel Kkiapay ---
            with transaction.atomic():
                try:
                    kkiapay_api_endpoint = f"{settings.KKIAPAY_API_BASE_URL}/payouts"
                    headers = {
                        'Content-Type': 'application/json',
                        'X-API-KEY': settings.KKIAPAY_SECRET_KEY,
                        'X-Merchant-ID': settings.KKIAPAY_MERCHANT_ID,
                    }

                    payload = {
                        'amount': float(retrait.montant),
                        'phone_number': retrait.numero_beneficiaire,
                        'currency': 'XOF',
                        'external_id': str(retrait.id),
                        'reason': f"Retrait de gains pour {retrait.nom_beneficiaire} {retrait.prenom_beneficiaire or ''}",
                    }

                    kkiapay_response = requests.post(kkiapay_api_endpoint, headers=headers, json=payload, timeout=30)
                    kkiapay_response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP

                    kkiapay_data = kkiapay_response.json()

                    if kkiapay_data.get('status') == 'SUCCESS': 
                        retrait.statut = 'approuve'
                        retrait.date_traitement = timezone.now()
                        retrait.transaction_id_fournisseur = kkiapay_data.get('transactionId')
                        message_retour = "Votre retrait a été effectué avec succès via Kkiapay."
                        http_status = status.HTTP_201_CREATED
                    else:
                        retrait.statut = 'rejete'
                        retrait.date_traitement = timezone.now()
                        retrait.message_echec = kkiapay_data.get('message', 'Échec du décaissement via Kkiapay (raison non spécifiée).')
                        message_retour = f"Le décaissement a échoué: {retrait.message_echec}"
                        http_status = status.HTTP_400_BAD_REQUEST

                    retrait.save() 

                except requests.exceptions.RequestException as e:
                    retrait.statut = 'rejete'
                    retrait.date_traitement = timezone.now()
                    retrait.message_echec = f"Erreur de connexion à Kkiapay ou réponse invalide : {e}"
                    retrait.save()
                    message_retour = f"Échec du décaissement : Problème de communication avec le service de paiement. {e}"
                    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

                except Exception as e:
                    retrait.statut = 'rejete'
                    retrait.date_traitement = timezone.now()
                    retrait.message_echec = f"Erreur interne lors du traitement du décaissement : {e}"
                    retrait.save()
                    message_retour = f"Échec du décaissement : Une erreur inattendue est survenue. {e}"
                    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

            return Response(
                {
                    'message': message_retour,
                    'statut': retrait.statut,
                    'montant': str(retrait.montant),
                    'id': retrait.id,
                    'transaction_id_fournisseur': retrait.transaction_id_fournisseur,
                },
                status=http_status
            )

    except Exception as e:
        return Response(
            {'error': str(e), 'detail': 'Une erreur est survenue lors du traitement de la demande de retrait.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_citizen_wallet_data(request, citizen_id):
    if request.user.id != citizen_id and not request.user.is_staff:
        return Response(
            {'detail': 'Vous n\'êtes pas autorisé à consulter ce portefeuille.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        citizen = User.objects.get(id=citizen_id)
        if not hasattr(citizen, 'user_type') or citizen.user_type != 'citoyen':
            return Response(
                {'detail': 'L\'utilisateur demandé n\'est pas un citoyen.'},
                status=status.HTTP_404_NOT_FOUND
            )

        collectes_citoyen = Collecte.objects.filter(citoyen=citizen)
        
        total_points_vert = collectes_citoyen.aggregate(Sum('point_vert'))['point_vert__sum'] or 0
        total_points_jaune = collectes_citoyen.aggregate(Sum('point_jaune'))['point_jaune__sum'] or 0
        total_points_noir = collectes_citoyen.aggregate(Sum('point_noir'))['point_noir__sum'] or 0

        total_points_from_collectes = total_points_vert + total_points_jaune + total_points_noir

        TAUX_CONVERSION_POINT_CFA = Decimal('0.16')
        gains_theoriques_cfa = Decimal(total_points_from_collectes) * TAUX_CONVERSION_POINT_CFA

        total_retraits_citoyen_effectues = Retrait.objects.filter(
            citoyen=citizen, 
            statut__in=['approuve', 'en_attente', 'complete_kkiapay']
        ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.00')

        solde_actuel_disponible_cfa = gains_theoriques_cfa - total_retraits_citoyen_effectues

        response_data = {
            'total_gains_points': total_points_from_collectes,
            'current_balance_cfa': str(solde_actuel_disponible_cfa.quantize(Decimal('0.01'))),
            'sac_vert': f"{total_points_vert} points",
            'sac_jaune': f"{total_points_jaune} points",
            'sac_noir': f"{total_points_noir} points",
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response(
            {'detail': 'Citoyen non trouvé.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"CRITICAL ERROR in get_citizen_wallet_data: {e}")
        traceback.print_exc() # Affiche la pile d'appels complète pour le débogage
        return Response(
            {'detail': f'Une erreur inattendue est survenue: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# --- Vue pour la demande de retrait par un CITOYEN avec Kkiapay ---
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_withdrawal_citizen(request):
    print(f"DEBUG: Requête POST reçue pour create_withdrawal_citizen. User: {request.user.username} (ID: {request.user.id}), Type: {request.user.user_type}")

    if not hasattr(request.user, 'user_type') or request.user.user_type != 'citoyen':
        print(f"DEBUG: Accès refusé - L'utilisateur n'est pas un citoyen. Type actuel: {request.user.user_type}")
        return Response(
            {'detail': 'Accès refusé. Seuls les citoyens peuvent demander un retrait via cette méthode.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = RetraitCitoyenSerializer(data=request.data, context={'request': request})

    try:
        if serializer.is_valid(raise_exception=True):
            montant_a_retirer = serializer.validated_data['montant'] # 'montant' est le champ du modèle, mappé depuis 'montant_demande'
            numero_beneficiaire = serializer.validated_data['numero_beneficiaire']
            nom_beneficiaire = serializer.validated_data['nom_beneficiaire']
            prenom_beneficiaire = serializer.validated_data.get('prenom_beneficiaire', '')
            nom_complet = f"{nom_beneficiaire} {prenom_beneficiaire}".strip()

            # --- DÉBUT DE L'INTÉGRATION KKIAYAPAY ---
            kkiapay_payout_url = f"{settings.KKIAPAY_API_BASE_URL}/payout"
            headers = {
                "X-API-KEY": settings.KKIAPAY_SECRET_KEY,
                "Content-Type": "application/json",
                'X-Merchant-ID': settings.KKIAPAY_MERCHANT_ID,
            }
            payload = {
                "amount": float(montant_a_retirer),
                "phone": numero_beneficiaire,
                "reason": f"Retrait de fonds GreenAct par {nom_complet}",
            }

            print(f"DEBUG (Kkiapay): Envoi de la requête de paiement à {kkiapay_payout_url} avec le payload : {payload}")
            kkiapay_response = requests.post(kkiapay_payout_url, headers=headers, json=payload, timeout=10) # Ajout d'un timeout

            # --- AJOUT DES LIGNES POUR INSPECTER LA RÉPONSE BRUTE ET GÉRER L'ERREUR JSON ---
            print(f"DEBUG (Kkiapay): Code de statut de la réponse brute Kkiapay : {kkiapay_response.status_code}")
            print(f"DEBUG (Kkiapay): En-têtes de la réponse brute Kkiapay : {kkiapay_response.headers}")
            print(f"DEBUG (Kkiapay): Texte de la réponse brute Kkiapay : {kkiapay_response.text}")

            transaction_id = None
            error_message = None
            retrait_statut = 'echec_kkiapay' # Par défaut en échec avant traitement réussi
            message = 'Échec de la transaction Kkiapay.'
            response_status = status.HTTP_400_BAD_REQUEST

            try:
                kkiapay_response_data = kkiapay_response.json()
                print(f"DEBUG (Kkiapay): Données de la réponse JSON Kkiapay : {kkiapay_response_data}")

                if kkiapay_response.status_code == 200 and kkiapay_response_data.get("status") == "success":
                    retrait_statut = 'complete_kkiapay'
                    message = 'Votre retrait a été traité avec succès par Kkiapay.'
                    response_status = status.HTTP_201_CREATED
                    transaction_id = kkiapay_response_data.get("transactionId")
                else:
                    error_message = kkiapay_response_data.get("message", kkiapay_response_data.get("error", "Erreur inconnue de Kkiapay"))
                    message = f'Échec du retrait via Kkiapay: {error_message}'

            except requests.exceptions.JSONDecodeError as json_e:
                print(f"ERROR (Kkiapay JSONDecodeError): Impossible de décoder la réponse JSON de Kkiapay: {json_e}")
                print(f"ERROR (Kkiapay JSONDecodeError): Texte de la réponse reçue: '{kkiapay_response.text[:200]}...'") # Afficher les 200 premiers caractères du texte brut
                error_message = f"Kkiapay a renvoyé une réponse non-JSON ou mal formée. Code statut: {kkiapay_response.status_code}. Détails: {json_e}"
                message = f'Échec du retrait via Kkiapay: {error_message}'

            # --- FIN DE L'INTÉGRATION KKIAYAPAY ---

            print(f"DEBUG: Tentative de sauvegarde du retrait avec statut: {retrait_statut}. Assignation de citoyen à {request.user.username} ({request.user.id})")
            retrait = serializer.save(
                citoyen=request.user, 
                collecteur=None,    
                statut=retrait_statut,
                date_demande=timezone.now(),
                transaction_id_fournisseur=transaction_id,
                message_echec=error_message,
                date_traitement=timezone.now() if retrait_statut in ['complete_kkiapay', 'echec_kkiapay'] else None,
            )
            print(f"DEBUG: Retrait sauvegardé avec ID: {retrait.id}, Statut: {retrait.statut}")

            return Response(
                {
                    'message': message,
                    'statut': retrait.statut,
                    'montant': str(retrait.montant), # Utilisez le champ 'montant' du modèle ici
                    'id': retrait.id,
                    'transaction_id_fournisseur': retrait.transaction_id_fournisseur
                },
                status=response_status
            )

    except requests.exceptions.RequestException as e:
        print(f"ERROR (RequestException): Erreur de connexion à Kkiapay ou problème HTTP: {str(e)}")
        traceback.print_exc()
        # Ne tentez pas de créer un Retrait ici si la connexion a échoué complètement
        return Response(
            {'error': 'Erreur de connexion à Kkiapay', 'detail': 'Une erreur est survenue lors de la tentative de paiement. Veuillez réessayer plus tard.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except ValidationError as e:
        print(f"DEBUG: Erreur de validation du serializer: {e.detail}")
        return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"CRITICAL ERROR (Unhandled): Erreur inattendue dans create_withdrawal_citizen: {e}")
        traceback.print_exc()

        # Tentative de sauvegarder l'échec si l'objet retrait n'a pas été créé ou sauvegardé précédemment
        try:
            # Vérifiez si un retrait a déjà été créé et peut être mis à jour
            if 'retrait' in locals() and hasattr(retrait, 'pk') and retrait.pk:
                retrait.statut = 'echec_interne' # Nouveau statut pour les erreurs internes
                retrait.message_echec = f"Erreur interne non gérée: {str(e)}"
                retrait.save()
                print(f"DEBUG: Retrait {retrait.id} mis à jour avec statut 'echec_interne'.")
            else:
                # Si l'erreur est survenue avant que 'retrait' ne soit créé ou sauvegardé
                # Utilisez request.data pour récupérer le montant_demande pour l'enregistrement de l'échec
                Retrait.objects.create(
                    citoyen=request.user,
                    collecteur=None,
                    montant=request.data.get('montant_demande', Decimal('0.00')), # Utilisez 'montant_demande' ici
                    nom_beneficiaire=request.data.get('nom_beneficiaire', 'Inconnu'),
                    numero_beneficiaire=request.data.get('numero_beneficiaire', 'N/A'),
                    statut='echec_interne',
                    message_echec=f"Erreur interne non gérée avant sauvegarde: {str(e)}",
                    date_demande=timezone.now(),
                    date_traitement=timezone.now()
                )
                print(f"DEBUG: Nouveau retrait 'echec_interne' créé pour un échec non géré.")
        except Exception as db_e:
            print(f"ERROR: Impossible de sauvegarder l'état d'échec du retrait (erreur de DB): {db_e}")
            traceback.print_exc()

        return Response(
            {'error': 'Une erreur interne est survenue lors du traitement de votre demande de retrait.', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


#customuser vue 

class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer 
    permission_classes = [IsAuthenticated] # seuls les utilisateurs authentifiés peuvent accéder

    def get_queryset(self):
        # Récupère le queryset par défaut (tous les utilisateurs)
        queryset = super().get_queryset()

        # Permet de filtrer par 'user_type' via le paramètre de requête 'user_type'
        # Exemple d'URL: /api/users/?user_type=citoyen
        user_type = self.request.query_params.get('user_type')
        if user_type is not None:
            queryset = queryset.filter(user_type=user_type)

      
        if self.request.user.is_authenticated:
            if self.request.user.user_type == 'admin':
                return queryset # Les admins voient tout
            else:
                # Les autres types d'utilisateurs ne voient que leur propre profil
                return queryset.filter(id=self.request.user.id)
        return queryset.none() # Ou gérer le cas des utilisateurs non authentifiés si nécessaire


   #vue de notifi

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        print("\n--- Début get_queryset ---")
        queryset = super().get_queryset() # Commence avec le queryset de base
        print(f"Queryset initial (avant filtres spécifiques) count: {queryset.count()}")

        # Filtrer par destinataire si le paramètre 'recipient' est fourni dans l'URL
        recipient_id = self.request.query_params.get('recipient')
        if recipient_id:
            print(f"Paramètre recipient_id détecté: {recipient_id}")
            try:
                # Tente de convertir l'ID en entier et de filtrer
                queryset = queryset.filter(recipient_id=int(recipient_id))
                print(f"Queryset après filtrage recipient: {queryset.count()} notifications")
            except ValueError:
                print(f"Erreur: recipient_id '{recipient_id}' n'est pas un entier valide.")
                return Notification.objects.none() # Retourne un queryset vide si l'ID est invalide

        # Filtrer par statut de lecture si le paramètre 'is_read' est fourni
        is_read_param = self.request.query_params.get('is_read')
        if is_read_param is not None:
            print(f"Paramètre is_read détecté: {is_read_param}")
            # Convertir la chaîne 'true'/'false' en booléen
            is_read_bool = is_read_param.lower() == 'true'
            queryset = queryset.filter(is_read=is_read_bool)
            print(f"Queryset après filtrage is_read ({is_read_bool}): {queryset.count()} notifications")

        # Assurez-vous que l'utilisateur authentifié ne voit que ses propres notifications
        # Cette logique est importante pour la sécurité.
        if self.request.user.is_authenticated:
            user_type = getattr(self.request.user, 'user_type', 'N/A') # Utiliser getattr pour éviter AttributeError
            print(f"Utilisateur authentifié: {self.request.user.username}, Type: {user_type}")

            # Permettre aux citoyens et aux collecteurs de voir leurs propres notifications
            if user_type in ['citoyen', 'collector']: # <-- AJOUTÉ: 'collector' ici
                queryset = queryset.filter(recipient=self.request.user)
                print(f"Queryset après filtrage par utilisateur ({user_type}): {queryset.count()} notifications")
            elif user_type == 'admin':
                print("Utilisateur est un admin. Pas de filtrage supplémentaire basé sur l'utilisateur (admin voit tout).")
                # L'admin peut voir toutes les notifications, ou celles qu'il est autorisé à voir.
                # Si vous voulez que l'admin ne voie que les siennes, ajoutez: queryset = queryset.filter(recipient=self.request.user)
                pass
            else:
                print("Type d'utilisateur non reconnu ou non défini. Retourne un queryset vide.")
                queryset = Notification.objects.none()
        else:
            print("Utilisateur non authentifié. Retourne un queryset vide.")
            queryset = Notification.objects.none()

        print(f"Queryset final retourné par get_queryset: {queryset.count()}")
        print("--- Fin get_queryset ---\n")
        return queryset.order_by('-created_at') # Ordonner par les plus récentes en premier


    # Action personnalisée pour marquer une notification comme lue
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        print(f"\n--- Début mark_as_read pour PK: {pk} ---")
        try:
            notification = self.get_object()
            print(f"Notification trouvée: ID={notification.id}, is_read={notification.is_read}, Recipient={notification.recipient.username}")

            if request.user.is_authenticated:
                user_type = getattr(request.user, 'user_type', 'N/A')
                print(f"Utilisateur requérant: {request.user.username}, Type: {user_type}")

                if notification.recipient == request.user or user_type == 'admin':
                    notification.is_read = True
                    notification.save()
                    print(f"Notification ID={notification.id} marquée comme lue et sauvegardée. Nouveau is_read: {notification.is_read}")
                    return Response({'status': 'notification marquée comme lue'}, status=status.HTTP_200_OK)
                else:
                    print("Permission refusée: L'utilisateur n'est pas le destinataire et n'est pas un admin.")
                    return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            else:
                print("Permission refusée: Utilisateur non authentifié.")
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        except Notification.DoesNotExist:
            print(f"Erreur: Notification avec PK={pk} non trouvée.")
            return Response({'error': 'Notification non trouvée'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Erreur inattendue dans mark_as_read: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            print("--- Fin mark_as_read ---\n")


  #vues de planification de collecte 
class PlanificationCollecteViewSet(viewsets.ModelViewSet):
     permission_classes = [IsAuthenticated] 
     queryset = PlanificationCollecte.objects.all()
     serializer_class = PlanificationCollecteSerializer

class CollectorViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.filter(user_type='collector')
    serializer_class = CollectorRegistrationSerializer
    permission_classes = [IsAdminUser] 



class CitizenRegistrationView(generics.CreateAPIView):
    serializer_class = CitizenRegistrationSerializer

    def post(self, request):
        email = request.data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            return Response(
                {'error': "L'email est deja utilise. Veuillez en choisir un autre."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                return Response(
                    {'success': True, 'message': 'Compte cree avec succes'},
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                return Response(
                    {'error': f"Une erreur est survenue: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            error_messages = ""
            for field, errors in serializer.errors.items():
                for error in errors:
                    error_messages += f"{field}: {error} "
            return Response(
                {'error': error_messages.strip()},
                status=status.HTTP_400_BAD_REQUEST
            )

from django.core.exceptions import ObjectDoesNotExist

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            access_token = serializer.validated_data['access']
            response_data = {
                'success': True,
                'message': 'Connexion réussie',
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.user_type,
                'token': access_token,
            }

            if user.user_type == 'citoyen':
                try:
                    # Récupérer la dernière attribution de sacs pour le citoyen
                    sac_citoyen = SacCitoyen.objects.filter(citoyen=user).order_by('-date_reception').first()
                    if sac_citoyen:
                        response_data.update({
                            'adresse': sac_citoyen.adresse,
                            'sac_vert': sac_citoyen.sac_vert,
                            'sac_jaune': sac_citoyen.sac_jaune,
                            'sac_noir': sac_citoyen.sac_noir,
                               'date_reception':sac_citoyen.date_reception       
                        })


                except ObjectDoesNotExist:
                    # Aucun enregistrement de sacs trouvé pour ce citoyen
                    pass  # Les champs d'attribution resteront absents ou null implicitement
                except Exception as e:
                    print(f"Erreur lors de la récupération de l'attribution des sacs : {e}")

            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CollectorRegistrationView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        serializer = CollectorRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            # Générer un ID formatte unique pour le collecteur
            prefix = 'COL/'
            while True:
                random_id = get_random_string(length=3, allowed_chars='0123456789')
                collector_id = prefix + random_id
                if not CustomUser.objects.filter(id_formatte=collector_id).exists():
                    break

            # Générer un mot de passe aléatoire
            random_password = get_random_string(length=12)

            # Créer le nouveau collecteur
            collector = CustomUser.objects.create(
                id_formatte=collector_id,
                username=serializer.validated_data['username'],
                email=serializer.validated_data['email'],
                adresse=serializer.validated_data['adresse'],
                user_type='collector',
                is_staff=True  # Leur donner le statut staff pour potentiellement accéder à l'admin limité
            )
            collector.set_password(random_password)
            collector.save()

            # Envoyer l'ID et le mot de passe au collecteur par e-mail
            subject = 'Vos informations de connexion'
            message = f"Votre identifiant de connexion est : {collector_id}\nVotre mot de passe temporaire est : {random_password}\n\nVeuillez changer votre mot de passe lors de votre première connexion."
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [collector.email]

            try:
                send_mail(subject, message, from_email, recipient_list, fail_silently=False)
                email_sent = True
            except Exception as e:
                email_sent = False
                print(f"Erreur lors de l'envoi de l'e-mail : {e}")

            response_data = {
                'success': True,
                'message': f'Collecteur enregistré avec succès. ID: {collector_id}.',
                'collector_id': collector_id,
            }
            if not email_sent:
                response_data['message'] += ' L\'e-mail d\'information n\'a pas pu être envoyé. Veuillez vérifier la configuration de votre e-mail.'

            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

  
# pour total des users
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated]) # nécessite une authentification
def total_users_count(request):
   
    total_users = CustomUser.objects.count()
    return Response({'total': total_users})









 
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import SacTri
import uuid

import logging
import random
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
# Configure le logger
logger = logging.getLogger(__name__)


def generate_numeric_id():
    """Génère un ID numérique aléatoire de 8 chiffres."""
    return str(random.randint(10000000, 99999999))



@csrf_exempt
def ajouter_sacs(request):
    """
    Ajoute un nouveau sac de tri.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            couleur = data.get('couleur')
            if not couleur:
                error_message = 'Le champ "couleur" est requis.'
                logger.error(error_message)
                return JsonResponse({'error': error_message}, status=400)
            nouvel_id = generate_numeric_id()
            nouveau_sac = SacTri(idformatter_sac=nouvel_id, couleur=couleur)
            nouveau_sac.save()
            return JsonResponse({'id_sac': nouveau_sac.idformatter_sac}, status=201)

        except json.JSONDecodeError:
            error_message = "Données JSON invalides"
            logger.error(error_message, exc_info=True)
            return JsonResponse({'error': error_message}, status=400)
        except Exception as e:
            error_message = f"Erreur inattendue: {e}"
            logger.error(error_message, exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)
    else:
        error_message = "Méthode non autorisée"
        logger.error(error_message)
        return JsonResponse({'error': error_message}, status=405)



@csrf_exempt
def modifier_sac(request, id_sac):
    """
    Modifie le statut d'un sac de tri spécifique.
    """
    # Utilise idformatter_sac pour récupérer le sac
    sac = get_object_or_404(SacTri, idformatter_sac=id_sac)
    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            nouveau_statut = data.get('statut')
            if nouveau_statut not in ['Disponible', 'Utilisé']:
                error_message = 'Statut invalide'
                logger.error(error_message)
                return JsonResponse({'error': error_message}, status=400)
            sac.statut = nouveau_statut
            sac.save()
            return JsonResponse({'message': 'Statut du sac mis à jour avec succès'}, status=200)
        except json.JSONDecodeError:
            error_message = "Données JSON invalides"
            logger.error(error_message, exc_info=True)
            return JsonResponse({'error': error_message}, status=400)
        except Exception as e:
            error_message = f"Erreur inattendue: {e}"
            logger.error(error_message, exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)
    else:
        error_message = "Méthode non autorisée"
        logger.error(error_message)
        return JsonResponse({'error': error_message}, status=405)


@csrf_exempt
def supprimer_sac(request, id_sac):
    """
    Supprime un sac de tri spécifique.
    """
    # Utilise idformatter_sac pour récupérer le sac
    sac = get_object_or_404(SacTri, idformatter_sac=id_sac)
    if request.method == 'DELETE':
        sac.delete()
        return JsonResponse({'message': 'Sac supprimé avec succès'}, status=204)
    else:
        error_message = "Méthode non autorisée"
        logger.error(error_message)
        return JsonResponse({'error': error_message}, status=405)




# recharger la liste
@csrf_exempt 
def liste_sacs(request):
    if request.method == 'GET':
        try:
            sacs = SacTri.objects.all()
            sacs_data = [{
                'id_sac': sac.idformatter_sac,  
                'couleur': sac.couleur,
                'statut': sac.statut,
            } for sac in sacs]
            return JsonResponse(sacs_data, safe=False, status=200) 
        except Exception as e:
            print(f"Erreur lors de la récupération des sacs: {e}")
            return JsonResponse({'error': 'Erreur interne du serveur'}, status=500)
    else:
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)



# total sacs
@api_view(['GET'])
def get_sac_count(request):
    """
    Renvoie le nombre total de sacs dans la base de données.
    """
    try:
        total_sacs = SacTri.objects.count() 
        return Response({'total': total_sacs}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': f'Une erreur s\'est produite : {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


#view pour collecte
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Collecte
from .serializers import CollecteSerializer
from django.shortcuts import get_object_or_404
from django.db.models import Q,F
from rest_framework.decorators import action
from django.db.models import Count
from django.db.models import Sum
from django.contrib.auth import get_user_model
User = get_user_model()


class CollecteViewSet(viewsets.ModelViewSet):
    serializer_class = CollecteSerializer
    
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Renvoie toutes les collectes pour les administrateurs,
        et seulement les collectes du collecteur authentifié pour les collecteurs.
        """
        if self.request.user.user_type == 'administrateur':
            return Collecte.objects.all()
        elif self.request.user.user_type == 'collecteur':
            return Collecte.objects.filter(collecteur=self.request.user)
        else:
            return Collecte.objects.none()

    def get_object(self):
        """
        Récupère l'objet Collecte en utilisant la clé primaire de l'URL.
        """
        queryset = Collecte.objects.all()  # Récupère tous les objets Collecte
        pk = self.kwargs.get('pk')  # Récupère la clé primaire de l'URL
        return get_object_or_404(queryset, pk=pk)  # Récupère l'objet ou renvoie une 404

    

    def perform_create(self, serializer):
        print("perform_create est appelé !")
        serializer.save(collecteur=self.request.user)
        citoyen = serializer.validated_data['citoyen']
        collecteur = self.request.user
        print(f"Citoyen: {citoyen}, Collecteur: {collecteur}")

        # Compter le nombre de collectes existantes pour ce citoyen et ce collecteur
        nombre_collectes = Collecte.objects.filter(citoyen=citoyen, collecteur=collecteur).count()
        print(f"Nombre de collectes existantes: {nombre_collectes}")

        # Mettre à jour le champ total_collectes_collecteur_citoyen de la NOUVELLE collecte
        serializer.instance.total_collectes_collecteur_citoyen = nombre_collectes
        print(f"Total des collectes à sauvegarder (sans incrémenter la nouvelle): {serializer.instance.total_collectes_collecteur_citoyen}")
        serializer.instance.save()

    @action(detail=False, methods=['get'])
    def get_collecte_by_citoyen(self, request):
        """
        Vérifie si une collecte existe pour un citoyen donné.
        """
        citoyen_id = request.query_params.get('citoyen_id')
        if not citoyen_id:
            return Response({'error': 'Le paramètre citoyen_id est requis.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            existing_collecte = Collecte.objects.filter(
                Q(citoyen_id=citoyen_id),
                Q(statut='en_attente') | Q(statut='en_cours') | Q(statut='en_cours_scan')
            ).first()

            if existing_collecte:
                serializer = self.get_serializer(existing_collecte)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'Aucune collecte existante trouvée pour ce citoyen.'}, status=status.HTTP_204_NO_CONTENT)  # Retourne 204 si pas de contenu

        except Collecte.DoesNotExist:
            return Response({'message': 'Aucune collecte existante trouvée pour ce citoyen.'}, status=status.HTTP_204_NO_CONTENT)  # Gestion DoesNotExist
        except Exception as e:
            return Response({'error': f'Une erreur s\'est produite : {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='historique-collecteur') 
    def get_historique_collecteur(self, request):
        """
        Renvoie l'historique des collectes pour le collecteur connecté.
        """
        print(f"User type: {self.request.user.user_type}")
        if self.request.user.user_type == 'collector':
            collectes = Collecte.objects.filter(collecteur=self.request.user)
            serializer = self.get_serializer(collectes, many=True)  
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Vous n\'êtes pas un collecteur.'}, status=status.HTTP_403_FORBIDDEN)
        
    @action(detail=False, methods=['get'], url_path='total-collectes-collecteur')
    def get_total_collectes_collecteur(self, request):
        """
        Renvoie le nombre total de collectes terminées effectuées par le collecteur connecté.
        """
        if request.user.user_type == 'collector':
            total_collectes = Collecte.objects.filter(
                collecteur=request.user,
                statut='termine' 
            ).count() 
            return Response({'total_collectes': total_collectes}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Vous n\'êtes pas un collecteur.'}, status=status.HTTP_403_FORBIDDEN)
   
    @action(detail=True, methods=['patch'], url_path='incrementer-points')
    def incrementer_points(self, request, pk=None):
        print("Méthode incrementer_points appelée !")
        print(f"ID de la collecte: {pk}")
        print(f"Données de la requête: {request.data}")
        try:
            collecte = self.get_object()
            print(f"Objet Collecte récupéré: {collecte}")

            point_vert_nouveaux = request.data.get('point_vert', 0)
            point_jaune_nouveaux = request.data.get('point_jaune', 0)
            point_noir_nouveaux = request.data.get('point_noir', 0)

            print(f"Points reçus: Vert={point_vert_nouveaux}, Jaune={point_jaune_nouveaux}, Noir={point_noir_nouveaux}")

            collecte.point_vert += point_vert_nouveaux
            collecte.point_jaune += point_jaune_nouveaux
            collecte.point_noir += point_noir_nouveaux
            collecte.statut = 'termine'
            collecte.save()
            print(f"Points de la collecte après incrémentation: Vert={collecte.point_vert}, Jaune={collecte.point_jaune}, Noir={collecte.point_noir}, Statut={collecte.statut}")

            serializer = self.get_serializer(collecte)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Collecte.DoesNotExist:
            print(f"Erreur: Collecte avec l'ID {pk} non trouvée.")
            return Response({'error': 'Collecte non trouvée.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Erreur inattendue lors de l'incrémentation des points: {e}")
            return Response({'error': f'Une erreur s\'est produite : {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
       

    @action(detail=False, methods=['get'], url_path='count-all')
    def count_all(self, request):
        """
        Renvoie le nombre total de collectes dans la base de données.
        """
        total_collectes = Collecte.objects.all().count()
        return Response({'total': total_collectes}, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'], url_path='total-points')
    def total_points(self, request):
        """
        Renvoie la somme totale des points (vert, jaune, noir) de toutes les collectes.
        """
        total_points = Collecte.objects.aggregate(
        total_vert=Sum('point_vert'),
        total_jaune=Sum('point_jaune'),
        total_noir=Sum('point_noir')
        )
        somme_totale_points = (total_points['total_vert'] or 0) + \
                               (total_points['total_jaune'] or 0) + \
                               (total_points['total_noir'] or 0)
        return Response({'total_points': somme_totale_points}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='points-citoyen/(?P<citizen_id>\d+)')
    def get_points_citoyen(self, request, citizen_id=None):
        """
        Récupère le total des points (vert, jaune, noir) et la date de la toute dernière collecte
        pour un citoyen spécifique.
        """
        try:
            citoyen = get_object_or_404(User, id=citizen_id)
        except ValueError:
            return Response({'erreur': 'ID de citoyen invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        # Agrégé les points totaux
        points_totaux = Collecte.objects.filter(citoyen=citoyen).aggregate(
            total_vert=Sum('point_vert'),
            total_jaune=Sum('point_jaune'),
            total_noir=Sum('point_noir')
        )

        # Récupère la date de la collecte la plus récente (quelle que soit la couleur du sac)
        derniere_collecte = Collecte.objects.filter(citoyen=citoyen).order_by('-date_collecte').first()

        date_derniere_collecte_str = 'N/A'
        if derniere_collecte:
            # Formate la date au format 'AAAA-MM-JJ HH:MM' pour une lecture facile
            date_derniere_collecte_str = derniere_collecte.date_collecte.strftime('%Y-%m-%d %H:%M')


        return Response({
            'sac_vert': f"{points_totaux['total_vert'] or 0} points",
            'sac_jaune': f"{points_totaux['total_jaune'] or 0} points",
            'sac_noir': f"{points_totaux['total_noir'] or 0} points",
            'date_derniere_collecte': date_derniere_collecte_str, # Clé renommée pour plus de clarté
        }, status=status.HTTP_200_OK)

#A refaire ...
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .models import SacTri
from django.http import JsonResponse  

class SacTriViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated] 

    def list(self, request):
        """
        Récupère la liste de tous les sacs (pour consultation éventuelle).
        """
        sacs = SacTri.objects.all()
        data = [{'idformatter_sac': sac.idformatter_sac, 'couleur': sac.couleur, 'statut': sac.statut} for sac in sacs]
        return Response(data)

    def retrieve(self, request, pk=None):
        """
        Récupère un sac spécifique par son ID formatter (pk).
        """
        try:
            sac = get_object_or_404(SacTri, idformatter_sac=pk)
            data = {'idformatter_sac': sac.idformatter_sac, 'couleur': sac.couleur, 'statut': sac.statut}
            return Response(data)
        except SacTri.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='marquer-sac-utilise')
    def marquer_sac_utilise(self, request):
        """
        Marque un sac comme 'Utilisé' après la lecture de son QR code.
        """
        id_sac_scanne = request.data.get('id_sac')

        if not id_sac_scanne:
            return Response({'error': 'L\'ID du sac est requis.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sac = get_object_or_404(SacTri, idformatter_sac=id_sac_scanne)
        except SacTri.DoesNotExist:
            return Response({'error': 'Le sac avec cet ID n\'existe pas.'}, status=status.HTTP_404_NOT_FOUND)

        if sac.statut == 'Utilisé':
            return Response({'message': 'Ce sac est déjà marqué comme utilisé.'}, status=status.HTTP_200_OK)
        else:
            sac.statut = 'Utilisé'
            sac.save()
            data = {'idformatter_sac': sac.idformatter_sac, 'couleur': sac.couleur, 'statut': sac.statut}
            return Response(data, status=status.HTTP_200_OK)


from django.contrib.auth import get_user_model
from .serializers import CustomUserSerializer  

CustomUser = get_user_model()  
@api_view(['GET'])
def get_collecteur(request, pk):
    try:
        collecteur = CustomUser.objects.get(pk=pk)
        serializer = CustomUserSerializer(collecteur)
        return Response(serializer.data)
    except CustomUser.DoesNotExist:
        return Response({'error': 'Collecteur non trouvé.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Une erreur s\'est produite : {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminCollecteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CollecteSerializer
    permission_classes = [IsAuthenticated, IsAdminUser] 

    def get_queryset(self):
        """
        Renvoie toutes les collectes pour les administrateurs.
        """
        return Collecte.objects.all()
    

  
