from django.core.validators import RegexValidator
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission

# Validator pour l'utilisateur avec lettres et espaces uniquement
letters_and_spaces = RegexValidator(
    regex=r'^[A-Za-zÀ-ÿ\s]+$',
    message="Le nom d'utilisateur doit contenir uniquement des lettres et des espaces."
)

class CustomUser(AbstractUser):
    username = models.CharField(
        max_length=150,
        unique=False,
        null=True,
        blank=True,
        validators=[letters_and_spaces],
        verbose_name="Nom d'utilisateur"
    )
    id_formatte = models.CharField(
        max_length=10,
        unique=True,
        null=False,
        blank=False,
        verbose_name="ID Formaté"
    )
    email = models.EmailField(
        unique=False,
        verbose_name="Adresse Email"
    )
    adresse = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Adresse"
    )
    user_type = models.CharField (
        max_length=20,
        choices=[
            ('citoyen', 'Citoyen'),
            ('admin', 'Administrateur'),
            ('collector', 'Collecteur'),
        ],
        default='citoyen',
        verbose_name="Type d'Utilisateur"
    )
    groups = models.ManyToManyField(Group, verbose_name=('groups'), blank=True, related_name='customuser_set')
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=('user permissions'),
        blank=True,
        related_name='customuser_set',
    )
    
    # Utilisation de l'ID formaté comme champ principal pour l'authentification
    USERNAME_FIELD = 'id_formatte'  
    REQUIRED_FIELDS = ['email','username']

    def __str__(self):
        return self.id_formatte or self.email




import random

def generate_numeric_id():
    """Génère un ID numérique aléatoire de 8 chiffres."""
    return str(random.randint(10000000, 99999999))

class SacTri(models.Model):
    idformatter_sac = models.CharField(
        max_length=8,
        primary_key=True,
        unique=True,
        verbose_name="ID formatter du sac",
        default=generate_numeric_id,  # Utilisez la fonction nommée
        editable=False
    )
    couleur = models.CharField(
        max_length=10,
        verbose_name="Couleur du sac",
        choices=[
            ('vert', 'Vert'),
            ('jaune', 'Jaune'),
            ('noir', 'Noir'),
        ]
    )
    statut = models.CharField(
        max_length=20,
        verbose_name="Statut du sac",
        default="Disponible",
        choices=[
            ('Disponible', 'Disponible'),
            ('Utilisé', 'Utilisé'),
        ]
    )

    def __str__(self):
        return self.idformatter_sac

    class Meta:
        verbose_name = "Sac"
        verbose_name_plural = "Sacs"



class SacCitoyen(models.Model):
    citoyen = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'user_type': 'citoyen'},
        related_name='sacs_recus',
        verbose_name="Citoyen"
    )
    sac_vert = models.IntegerField(
        default=0,
        verbose_name="Nombre de sacs verts"
    )
    sac_noir = models.IntegerField(
        default=0,
        verbose_name="Nombre de sacs noirs"
    )
    sac_jaune = models.IntegerField(
        default=0,
        verbose_name="Nombre de sacs jaunes"
    )
    adresse = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Adresse"
    )
    date_reception = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sac attribué au citoyen"
        verbose_name_plural = "Sacs attribués aux citoyens"
        unique_together = ('citoyen',)

    def __str__(self):
        return f"Sacs pour {self.citoyen.username} le {self.date_reception}"

from django.conf import settings  

from django.db import models
from django.conf import settings

class Collecte(models.Model):
    """Modèle représentant une collecte de sacs effectuée par un collecteur pour un citoyen."""

    STATUS_CHOICES = [
        ('en_attente', 'En attente'),
        ('en_cours', 'En cours'),
        ('en_cours_scan', 'En cours de scan'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
    ]

    citoyen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='collectes_citoyen',
        on_delete=models.CASCADE,
        limit_choices_to={'user_type': 'citoyen'},
        verbose_name="Citoyen"
    )
    collecteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='collectes_collecteur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'user_type': 'collecteur'},
        verbose_name="Collecteur"
    )
    date_collecte = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de collecte"
    )
    point_vert = models.IntegerField(
        default=0,
        verbose_name="Points sacs verts"
    )
    point_jaune = models.IntegerField(
        default=0,
        verbose_name="Points sacs jaunes"
    )
    point_noir = models.IntegerField(
        default=0,
        verbose_name="Points sacs noirs"
    )
    total_collectes_collecteur_citoyen = models.IntegerField(default=0, verbose_name="Total des collectes de ce collecteur pour ce citoyen")

    statut = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='en_attente',
        verbose_name="Statut de la collecte"
    )

    class Meta:
        verbose_name = "Collecte"
        verbose_name_plural = "Collectes"
        ordering = ['-date_collecte']  # Tri par date de collecte la plus récente par défaut

    def __str__(self):
        return f"Collecte du {self.date_collecte.strftime('%d/%m/%Y à %H:%M')} par {self.collecteur} pour {self.citoyen} (Statut: {self.get_statut_display()})"  



class PlanificationCollecte(models.Model):
    ville = models.CharField(max_length=100)
    quartier = models.CharField(max_length=100)
    date_collecte = models.DateField()
    heure_collecte = models.TimeField()
   
    collecteurs_assignes = models.ManyToManyField(CustomUser, related_name='planifications_collecte')

    class Meta:
        verbose_name = "Planification de Collecte"
        verbose_name_plural = "Planifications de Collecte"

    def __str__(self):
        return f"Collecte à {self.ville}, {self.quartier} le {self.date_collecte} à {self.heure_collecte}"

class Notification(models.Model):
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"Notification pour {self.recipient.username}: {self.message[:50]}..."


from django.contrib.auth import get_user_model 

User = get_user_model()
class Retrait(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('approuve', 'Approuvé'),
        ('rejete', 'Rejeté'),
        ('echec_kkiapay', 'Échec Kkiapay'),
        ('complete_kkiapay', 'Terminé par Kkiapay')
    ]
    
    collecteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='retraits_demandes_collecteur')
    
    citoyen = models.ForeignKey(User, on_delete=models.CASCADE, related_name='retraits_initie_citoyen', null=True, blank=True)    
    montant = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    nom_beneficiaire = models.CharField(max_length=100)
    prenom_beneficiaire = models.CharField(max_length=100, blank=True, null=True)
    numero_beneficiaire = models.CharField(max_length=20, null=True)
    date_demande = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_traitement = models.DateTimeField(null=True, blank=True)
    traite_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='retraits_traites')
    transaction_id_fournisseur = models.CharField(max_length=255, blank=True, null=True)
    message_echec = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.citoyen:
            return f"Retrait de {self.montant} CFA par Citoyen: {self.citoyen.get_full_name() or self.citoyen.username} - Statut: {self.get_statut_display()}"
        elif self.collecteur:
            return f"Retrait de {self.montant} CFA par Collecteur: {self.collecteur.get_full_name() or self.collecteur.username} - Statut: {self.get_statut_display()}"
        return f"Retrait de {self.montant} CFA (Demandeur inconnu) - Statut: {self.get_statut_display()}"

    @property
    def demandeur_full_name(self):
        #  propriété générique pour le demandeur, qu'il soit citoyen ou collecteur
        if self.citoyen:
            return self.citoyen.get_full_name() or self.citoyen.username
        elif self.collecteur:
            return self.collecteur.get_full_name() or self.collecteur.username
        return "N/A"

    @property
    def traite_par_full_name(self):
        return self.traite_par.get_full_name() or self.traite_par.username if self.traite_par else "N/A"

    