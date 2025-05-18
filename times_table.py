import json
import os
from ortools.sat.python import cp_model

class GenerateurEmploiDuTemps:
    def __init__(self):
        # Données de base
        self.jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
        self.periodes = ["P1 (7h-10h)", "P2 (10h-13h)", "P3 (13h-16h)", "P4 (16h-19h)", "P5 (19h-22h)"]
        self.poids_periodes = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1}  # Priorité aux cours du matin
        
        # Chargement des données
        try:
            with open('subjects.json', 'r', encoding='utf-8') as f:
                self.matieres_data = json.load(f)
            with open('rooms.json', 'r', encoding='utf-8') as f:
                self.salles_data = json.load(f)
                self.salles = self.salles_data["Informatique"]
            print("✓ Données chargées avec succès!")
        except Exception as e:
            print(f"❌ Erreur lors du chargement des données: {e}")
            exit(1)
    
    def extraire_matieres_niveau(self, niveau, semestre):
        try:
            return self.matieres_data["niveau"][str(niveau)][semestre]["subjects"]
        except KeyError:
            print(f"❌ Pas de données pour le niveau {niveau}, semestre {semestre}")
            return []
    
    def generer_emploi_du_temps(self, niveau, semestre):
        print(f"\n🔄 Génération EDT: Niveau {niveau}, Semestre {semestre}")
        
        # Récupération des matières
        matieres = self.extraire_matieres_niveau(niveau[0], semestre)
        if not matieres:
            return None
        
        # Filtrage des matières valides
        matieres = [m for m in matieres if (isinstance(m.get("name", ""), str) and m.get("name", "")) or 
                   (isinstance(m.get("name", ""), list) and any(m.get("name", "")))]
        
        print(f"📚 {len(matieres)} matières trouvées")
        
        # Création du modèle
        model = cp_model.CpModel()
        
        # Indices
        C = list(range(len(matieres)))            # Cours
        S = list(range(len(self.salles)))         # Salles
        J = list(range(len(self.jours)))          # Jours
        P = list(range(len(self.periodes)))       # Périodes
        N = [niveau[0]]                           # Niveaux
        
        # Enseignants
        enseignants = []
        for m in matieres:
            if "Course Lecturer" in m:
                if isinstance(m["Course Lecturer"], list):
                    for e in m["Course Lecturer"]:
                        if e and e not in enseignants:
                            enseignants.append(e)
                elif m["Course Lecturer"] and m["Course Lecturer"] not in enseignants:
                    enseignants.append(m["Course Lecturer"])
        
        if not enseignants:
            enseignants = ["Enseignant par défaut"]
        
        E = list(range(len(enseignants)))         # Ensemble des enseignants
        
        # Poids de chaque période
        W_p = [self.poids_periodes[p] for p in P]
        
        # Matrice curriculum
        S_lc = {(l, c): 1 for l in N for c in C}
        
        # Variable de décision
        X = {}
        for c in C:
            for s in S:
                for j in J:
                    for p in P:
                        for n in N:
                            for e in E:
                                X[(c, s, j, p, n, e)] = model.NewBoolVar(f'X_{c}_{s}_{j}_{p}_{n}_{e}')
        
        # Contrainte 1: Chaque cours programmé une fois par semaine
        for c in C:
            model.Add(sum(X[(c, s, j, p, n, e)] for s in S for j in J for p in P for n in N for e in E) == 1)
        
        # Contrainte 2: Pas de conflit de salle
        for s in S:
            for j in J:
                for p in P:
                    model.Add(sum(X[(c, s, j, p, n, e)] for c in C for n in N for e in E) <= 1)
        
        # Contrainte 3: Pas de conflit de niveau
        for n in N:
            for j in J:
                for p in P:
                    model.Add(sum(S_lc[(n, c)] * X[(c, s, j, p, n, e)] 
                             for c in C for s in S for e in E) <= 1)
        
        # Contrainte 4: Pas de conflit d'enseignant
        for e in E:
            for j in J:
                for p in P:
                    model.Add(sum(X[(c, s, j, p, n, e)] for c in C for s in S for n in N) <= 1)
        
        # Fonction objectif: Maximiser la préférence pour les périodes du matin
        objectif = []
        for c in C:
            for s in S:
                for j in J:
                    for p in P:
                        for n in N:
                            for e in E:
                                objectif.append(W_p[p] * X[(c, s, j, p, n, e)])
        
        model.Maximize(sum(objectif))
        
        # Résolution
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        
        # Récupération des résultats
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("✓ Solution trouvée!")
            
            emploi_du_temps = []
            for c in C:
                for s in S:
                    for j in J:
                        for p in P:
                            for n in N:
                                for e in E:
                                    if solver.Value(X[(c, s, j, p, n, e)]) == 1:
                                        emploi_du_temps.append({
                                            'cours': matieres[c],
                                            'jour': self.jours[j],
                                            'periode': self.periodes[p],
                                            'salle': self.salles[s],
                                            'niveau': n,
                                            'enseignant': enseignants[e]
                                        })
            
            return emploi_du_temps
        else:
            print("❌ Pas de solution trouvée.")
            return None
    
    def afficher_emploi_du_temps(self, emploi_du_temps):
        if not emploi_du_temps:
            print("❌ Pas d'emploi du temps à afficher.")
            return
        
        # Tri par jour puis par période
        jour_indices = {jour: idx for idx, jour in enumerate(self.jours)}
        periode_indices = {periode: idx for idx, periode in enumerate(self.periodes)}
        
        emploi_du_temps_trie = sorted(
            emploi_du_temps, 
            key=lambda x: (jour_indices[x["jour"]], periode_indices[x["periode"]])
        )
        
        # Affichage
        print("\n" + "="*100)
        print("📅 EMPLOI DU TEMPS".center(100))
        print("="*100)
        
        jour_courant = None
        for seance in emploi_du_temps_trie:
            if jour_courant != seance["jour"]:
                jour_courant = seance["jour"]
                print("\n" + "-"*100)
                print(f"📆 {jour_courant}".center(100))
                print("-"*100)
                print(f"{'HORAIRE':<15}{'COURS':<40}{'CODE':<10}{'ENSEIGNANT':<20}{'SALLE':<15}")
                print("-"*100)
            
            cours = seance["cours"]
            nom_cours = cours.get("name", "N/A")
            if isinstance(nom_cours, list):
                nom_cours = " ".join([n for n in nom_cours if n])
                
            code_cours = cours.get("code", "N/A")
            
            enseignant = seance.get("enseignant", "N/A")
            if not enseignant or enseignant == "N/A":
                if "Course Lecturer" in cours:
                    if isinstance(cours["Course Lecturer"], list):
                        enseignant = " ".join([e for e in cours["Course Lecturer"] if e])
                    else:
                        enseignant = cours["Course Lecturer"]
            
            periode = seance["periode"]
            salle = seance["salle"]["num"]
            
            # Limiter la longueur pour l'affichage
            if isinstance(nom_cours, str) and len(nom_cours) > 37:
                nom_cours = nom_cours[:34] + "..."
            
            if isinstance(enseignant, str) and len(enseignant) > 17:
                enseignant = enseignant[:14] + "..."
            
            print(f"{periode:<15}{nom_cours:<40}{code_cours:<10}{enseignant:<20}{salle:<15}")
        
        print("\n" + "="*100)
    
    def menu_principal(self):
        while True:
            print("\n" + "="*60)
            print("🏫 GÉNÉRATEUR D'EMPLOI DU TEMPS - UNIVERSITÉ DE YAOUNDÉ I".center(60))
            print("="*60)
            print("Choisissez un niveau et un semestre:")
            print("1. Licence 1 - Semestre 1")
            print("2. Licence 1 - Semestre 2")
            print("3. Licence 2 - Semestre 1")
            print("4. Licence 2 - Semestre 2")
            print("5. Licence 3 - Semestre 1")
            print("6. Licence 3 - Semestre 2")
            print("7. Master 1 - Semestre 1")
            print("8. Master 1 - Semestre 2")
            print("9. Master 2 - Semestre 1")
            print("10. Master 2 - Semestre 2")
            print("0. Quitter")
            print("-"*60)
            
            choix = input("Votre choix: ")
            
            if choix == '0':
                print("🔚 Merci d'avoir utilisé le générateur d'emploi du temps!")
                break
            
            try:
                choix = int(choix)
                if 1 <= choix <= 10:
                    niveau = (choix + 1) // 2
                    semestre = 's1' if choix % 2 == 1 else 's2'
                    emploi_du_temps = self.generer_emploi_du_temps([niveau], semestre)
                    self.afficher_emploi_du_temps(emploi_du_temps)
                else:
                    print("❌ Choix invalide. Veuillez réessayer.")
            except ValueError:
                print("❌ Entrée invalide. Veuillez entrer un nombre.")

def main():
    # Vérification des fichiers nécessaires
    if not os.path.exists('subjects.json') or not os.path.exists('rooms.json'):
        print("❌ Erreur: Les fichiers subjects.json et/ou rooms.json n'existent pas.")
        print("Veuillez placer ces fichiers dans le même dossier que ce script.")
        return
    
    # Lancement du générateur
    generateur = GenerateurEmploiDuTemps()
    generateur.menu_principal()

if __name__ == "__main__":
    main()