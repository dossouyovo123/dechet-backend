from rest_framework import serializers, viewsets
from rest_framework.response import Response
from django.db import models
from .models import SacCitoyen,CustomUser
from .serializers import UserSerializer, SacCitoyenSerializer
from rest_framework import status
from django.utils import timezone  
from .views import CollecteViewSet
from rest_framework import viewsets
from rest_framework import mixins


class CitoyenViewSet(viewsets.ReadOnlyModelViewSet, mixins.DestroyModelMixin):
    serializer_class = UserSerializer
    queryset = CustomUser.objects.filter(user_type='citoyen')

    def get_queryset(self):
        queryset = super().get_queryset()
        search_term = self.request.query_params.get('search', None)
        if search_term:
            queryset = queryset.filter(
                models.Q(username__icontains=search_term) |
                models.Q(email__icontains=search_term) |
                models.Q(id_formatte__icontains=search_term)
            )
        return queryset

from rest_framework import viewsets
from django.shortcuts import get_object_or_404

from django.db.models import ObjectDoesNotExist 

class AttributionSacsViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer l'attribution des sacs aux citoyens.
    """
    serializer_class = SacCitoyenSerializer
    queryset = SacCitoyen.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        citoyen_id = request.data.get('citoyen')
        citoyen = get_object_or_404(CustomUser, id=citoyen_id)

        try:
            # Tente de récupérer le premier enregistrement existant pour ce citoyen
            sac_citoyen = SacCitoyen.objects.filter(citoyen=citoyen).order_by('date_reception').first()  
            if sac_citoyen:
                # Mise à jour de l'instance existante
                sac_citoyen.sac_vert = serializer.validated_data['sac_vert']
                sac_citoyen.sac_noir = serializer.validated_data['sac_noir']
                sac_citoyen.sac_jaune = serializer.validated_data['sac_jaune']
                sac_citoyen.adresse = serializer.validated_data.get('adresse', sac_citoyen.adresse)
                sac_citoyen.save()

                serializer = self.get_serializer(sac_citoyen)
                return Response({'message': f'Informations mises à jour pour le citoyen {citoyen.username}.',
                                 'data': serializer.data}, status=status.HTTP_200_OK)
            else:
                 # Créer une nouvelle instance
                new_sac_citoyen = SacCitoyen.objects.create(
                    citoyen=citoyen,
                    sac_vert=serializer.validated_data['sac_vert'],
                    sac_noir=serializer.validated_data['sac_noir'],
                    sac_jaune=serializer.validated_data['sac_jaune'],
                    adresse=serializer.validated_data.get('adresse', "")
                )
                serializer = self.get_serializer(new_sac_citoyen)
                return Response({'message': f'Informations créées pour le citoyen {citoyen.username}.',
                                     'data': serializer.data}, status=status.HTTP_201_CREATED)
        except ObjectDoesNotExist: #gestion d'erreur
            # Créer une nouvelle instance
            new_sac_citoyen = SacCitoyen.objects.create(
                citoyen=citoyen,
                sac_vert=serializer.validated_data['sac_vert'],
                sac_noir=serializer.validated_data['sac_noir'],
                sac_jaune=serializer.validated_data['sac_jaune'],
                adresse=serializer.validated_data.get('adresse', "")
            )
            serializer = self.get_serializer(new_sac_citoyen)
            return Response({'message': f'Informations créées pour le citoyen {citoyen.username}.',
                                 'data': serializer.data}, status=status.HTTP_201_CREATED)
        except Exception as e: #gestion des autres erreurs
             return Response({'error': f'Une erreur s\'est produite: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
