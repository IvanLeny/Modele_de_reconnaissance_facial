# Projet de Reconnaissance Faciale - MDSMS1

## Groupe 1

• KAMATE Saranh Beh ; 
• ABONDO MEMANG Ivan Leny,  
• MODJARBA Habib 
•Messina ATA Mallory Noelle 

## Description
Système de reconnaissance faciale pour identifier les étudiants de la promotion MDSMS1 utilisant un modèle CNN.
## oprration de collecte
```
pour mettre sur pieds notre base de données , nous avons effectué des seances photo avec les etudiants
disponibles (8 etudiants), on a fait le maximum de photo possible par étudiant
ces photos ont été ensuite étiquetés de facon manuelle avant leur exploitation. c'est donc de cette façon qu'on a realisénotre base 
data/raw 
```
## Résultats
- **Accuracy sur le test set : 92.3%**
- **8 étudiants reconnus**
- **Modèle entraîné sur 128 images**

## Architecture
- **Modèle CNN** avec 3 couches de convolution
- **Input** : 128x128 pixels
- **Output** : 8 classes (étudiants)

## Structure du Projet
MDSMS1_Face_Reconnaissance /
├── data/
│ ├── raw/ # Images brutes (par étudiant)
│ ├── processed/ # Images prétraitées
│ └── labels/ # Mapping des labels
├── models/
│ └── face_recognition_model.h5 # Modèle entraîné
├── src/
│ ├── data_collection.py # Collecte des données
│ ├── preprocessing.py # Prétraitement
│ ├── training.py # Entraînement
│ ├── evaluation.py # Évaluation
│ └── prediction.py # Reconnaissance temps réel
└── README.md

## Utilisation

### Installation
```bash
pip install -r requirements.txt

Reconnaissance en temps réel
bash
python src/prediction.py
Test du modèle
bash
python src/evaluation.py
Étudiants reconnus
Abibe, Beindi, Destin, Jessy, Jordan, Kamate, Laurent, Mama

Performances par classe
Abibe: 100%

Beindi: 100%

Destin: 100%

Jessy: 67%

Jordan: 100%

Kamate: 100%

Laurent: 75%

Mama: 100%

Conclusion
Le modèle atteint 92.3% d'accuracy et peut reconnaître efficacement les étudiants de la classe.

text

##**Félicitations !** 

Notre projet de reconnaissance faciale est **OPÉRATIONNEL** avec :
- **92.3% d'accuracy** 
- **8/8 étudiants reconnus car certains étaient absents pendant la seance photo**
- **Modèle sauvegardé** (.h5)
- **Code complet et fonctionnel**

**Testez maintenant `python src\prediction.py` pour voir votre modèle en action !**