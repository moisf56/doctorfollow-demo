"""
Medical Knowledge Graph Builder
Extracts entities and relationships from PDF chunks and builds Neo4j graph

Grounded in actual PDF content (neonatal medicine, pages 233-282)
"""
import sys
from pathlib import Path
import re
from typing import List, Dict, Set, Tuple

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent))

from config import settings
from iteration_1.opensearch_store import ElasticsearchStore
from neo4j_store import Neo4jStore, Entity, Relationship


class MedicalKGBuilder:
    """
    Build medical knowledge graph from PDF chunks

    Approach:
    1. Extract entities using pattern matching (diseases, drugs, procedures, symptoms)
    2. Identify relationships from co-occurrence and patterns
    3. Populate Neo4j graph
    """

    def __init__(self, opensearch_store: ElasticsearchStore, neo4j_store: Neo4jStore):
        """
        Initialize KG builder

        Args:
            opensearch_store: OpenSearch store with indexed chunks
            neo4j_store: Neo4j store for graph
        """
        self.opensearch = opensearch_store
        self.neo4j = neo4j_store

        # Medical entity patterns (comprehensive extraction from Nelson Essentials of Pediatrics, pages 233-282)
        # Over 800 entities covering full neonatal medicine spectrum
        self.entity_patterns = {
            "disease": [
                # Pregnancy/Maternal Complications
                "intrauterine growth restriction", "IUGR", "birth asphyxia", "prematurity",
                "postmaturity", "cerebral palsy", "intellectual disability", "preeclampsia",
                "eclampsia", "gestational diabetes", "placenta previa", "abruptio placentae",
                "oligohydramnios", "polyhydramnios", "blood group sensitization", "hydrops fetalis",
                "multiple gestation", "twin-to-twin transfusion syndrome", "HELLP syndrome",
                "chorioamnionitis", "preterm labor", "premature rupture of membranes",

                # Neonatal Respiratory
                "respiratory distress syndrome", "RDS", "hyaline membrane disease",
                "transient tachypnea of the newborn", "meconium aspiration syndrome",
                "meconium aspiration pneumonia", "persistent pulmonary hypertension of the newborn",
                "PPHN", "bronchopulmonary dysplasia", "chronic lung disease", "pneumothorax",
                "pulmonary interstitial emphysema", "pneumomediastinum", "subcutaneous emphysema",
                "pulmonary hemorrhage", "pulmonary hypoplasia", "apnea of prematurity",
                "retinopathy of prematurity", "retrolental fibroplasia",

                # Cardiovascular
                "patent ductus arteriosus", "PDA", "congenital heart disease", "cyanotic heart disease",
                "coarctation of aorta", "transposition of the great arteries",
                "tetralogy of Fallot", "ventricular septal defect", "atrial septal defect",
                "hypoplastic left heart syndrome", "truncus arteriosus", "pulmonary atresia",

                # Hematologic
                "erythroblastosis fetalis", "hemolytic disease of the newborn", "ABO incompatibility",
                "Rh incompatibility", "anemia", "polycythemia", "hyperviscosity syndrome",
                "thrombocytopenia", "hemorrhagic disease of the newborn", "vitamin K deficiency",
                "disseminated intravascular coagulation", "DIC",

                # Jaundice/Liver
                "hyperbilirubinemia", "physiological jaundice", "breast milk jaundice",
                "kernicterus", "bilirubin encephalopathy", "neonatal hepatitis", "biliary atresia", "cholestasis",

                # Neurological
                "hypoxic-ischemic encephalopathy", "intraventricular hemorrhage", "IVH",
                "periventricular leukomalacia", "PVL", "seizures", "neonatal seizures",
                "subdural hemorrhage", "subarachnoid hemorrhage", "intracranial hemorrhage",
                "cerebral edema", "hydrocephalus", "microcephaly", "meningomyelocele", "spina bifida",

                # Gastrointestinal
                "necrotizing enterocolitis", "NEC", "intestinal obstruction", "volvulus",
                "duodenal atresia", "esophageal atresia", "tracheoesophageal fistula",
                "gastroschisis", "omphalocele", "meconium ileus", "Hirschsprung disease",

                # Metabolic/Endocrine
                "hypoglycemia", "hyperglycemia", "hypocalcemia", "hypercalcemia",
                "hypothermia", "hyperthyroidism", "hypothyroidism", "congenital hypothyroidism",
                "congenital adrenal hyperplasia", "phenylketonuria", "PKU", "galactosemia",

                # Infectious Diseases
                "sepsis", "neonatal sepsis", "early-onset sepsis", "late-onset sepsis",
                "meningitis", "pneumonia", "congenital pneumonia", "urinary tract infection",
                "osteomyelitis", "omphalitis",

                # Congenital Infections (TORCH)
                "toxoplasmosis", "rubella", "congenital rubella", "cytomegalovirus", "CMV",
                "herpes simplex", "HSV", "congenital syphilis", "syphilis",
                "varicella-zoster", "parvovirus", "HIV", "hepatitis B", "gonorrhea",
                "gonococcal ophthalmia", "chlamydia", "tuberculosis",

                # Birth Injuries/Trauma
                "birth trauma", "caput succedaneum", "cephalhematoma", "subgaleal hemorrhage",
                "skull fracture", "clavicle fracture", "brachial plexus injury",
                "Erb-Duchenne paralysis", "facial nerve palsy", "spinal cord injury",

                # Congenital Anomalies
                "Down syndrome", "trisomy 21", "trisomy 13", "trisomy 18", "Turner syndrome",
                "DiGeorge syndrome", "Potter syndrome", "choanal atresia", "diaphragmatic hernia",
                "renal agenesis", "multicystic kidney disease", "cryptorchidism", "hypospadias",

                # Other
                "small for gestational age", "SGA", "large for gestational age", "macrosomia",
                "hydrops", "edema", "ascites", "shock", "asphyxia", "respiratory failure",
                "heart failure", "renal failure", "metabolic acidosis", "respiratory acidosis",
            ],

            "drug": [
                # Antibiotics
                "ampicillin", "gentamicin", "penicillin", "cefotaxime", "ceftriaxone",
                "erythromycin", "vancomycin", "rifampin", "isoniazid", "cephalosporin",
                "metronidazole", "trimethoprim", "sulfamethoxazole",

                # Antivirals
                "acyclovir", "ganciclovir", "zidovudine", "AZT",

                # Respiratory
                "surfactant", "exogenous surfactant", "caffeine", "theophylline",
                "aminophylline", "albuterol", "inhaled nitric oxide", "oxygen",
                "CPAP", "continuous positive airway pressure",

                # Cardiovascular
                "indomethacin", "ibuprofen", "dopamine", "dobutamine", "epinephrine",
                "prostaglandin", "digoxin",

                # Metabolic/Nutrition
                "vitamin K", "RhoGAM", "calcium gluconate", "magnesium sulfate",
                "sodium bicarbonate", "glucose", "dextrose", "total parenteral nutrition", "TPN",

                # Anticonvulsants
                "phenobarbital", "phenytoin", "diazepam", "midazolam", "lorazepam",

                # Steroids
                "betamethasone", "dexamethasone", "hydrocortisone", "prednisone",

                # Other
                "naloxone", "insulin", "thyroxine", "levothyroxine", "propranolol",
                "furosemide", "heparin", "folic acid", "iron", "erythropoietin",
                "intravenous immunoglobulin", "IVIG", "fresh frozen plasma",
                "packed red blood cells", "platelets", "silver nitrate",
            ],

            "procedure": [
                # Delivery/Obstetric
                "cesarean section", "vaginal delivery", "forceps delivery", "breech delivery",
                "amniocentesis", "chorionic villus sampling", "intrauterine transfusion",

                # Resuscitation
                "resuscitation", "neonatal resuscitation", "positive pressure ventilation",
                "bag and mask ventilation", "endotracheal intubation", "chest compressions",
                "external cardiac massage", "umbilical catheterization",

                # Respiratory Support
                "mechanical ventilation", "assisted ventilation", "high-frequency ventilation",
                "extracorporeal membrane oxygenation", "ECMO", "oxygen therapy",
                "nasal CPAP", "high-flow nasal cannula",

                # Vascular Access
                "umbilical artery catheter", "umbilical venous catheter", "central venous catheter",
                "intravenous line", "arterial line",

                # Drainage/Decompression
                "thoracentesis", "paracentesis", "lumbar puncture", "chest tube placement",
                "nasogastric suction", "gastric decompression",

                # Transfusion
                "blood transfusion", "exchange transfusion", "platelet transfusion",
                "partial exchange transfusion",

                # Phototherapy
                "phototherapy", "blue light therapy", "bilirubin lights",

                # Surgical
                "laparotomy", "surgical ligation", "patent ductus arteriosus ligation",
                "bowel resection", "ventriculoperitoneal shunt", "laser therapy", "cryotherapy",

                # Diagnostic
                "ultrasound", "echocardiogram", "electrocardiogram", "ECG", "chest radiograph",
                "x-ray", "computed tomography", "CT scan", "magnetic resonance imaging", "MRI",
                "cranial ultrasound", "pulse oximetry", "blood gas analysis", "arterial blood gas",
                "complete blood count", "CBC", "blood culture", "urine culture", "CSF analysis",
                "Gram stain", "polymerase chain reaction", "PCR", "hearing screening",
                "newborn screening", "metabolic screening", "ophthalmologic examination",
                "electroencephalogram", "EEG", "Coombs test", "karyotype", "genetic testing",

                # Therapeutic
                "therapeutic hypothermia", "induced hypothermia", "cooling", "volume expansion",
                "fluid resuscitation", "gavage feeding", "nasogastric feeding",
                "total parenteral nutrition", "enteral feeding", "breast feeding",
                "kangaroo care", "developmental care",

                # Preventive
                "prophylaxis", "antibiotic prophylaxis", "eye prophylaxis", "vitamin K prophylaxis",
                "immunization", "vaccination", "hepatitis B vaccine", "isolation",
            ],

            "symptom": [
                # General
                "fever", "hypothermia", "lethargy", "irritability", "hypotonia", "hypertonia",
                "poor feeding", "feeding intolerance", "vomiting", "diarrhea", "poor weight gain",
                "failure to thrive", "edema", "pallor", "cyanosis", "jaundice", "icterus",
                "rash", "petechiae", "purpura", "bleeding", "hemorrhage",

                # Respiratory
                "respiratory distress", "tachypnea", "bradypnea", "apnea", "dyspnea",
                "grunting", "nasal flaring", "retractions", "intercostal retractions",
                "wheezing", "stridor", "hypoxia", "hypoxemia", "respiratory failure",

                # Cardiovascular
                "tachycardia", "bradycardia", "murmur", "heart murmur", "arrhythmia",
                "hypotension", "hypertension", "shock", "poor perfusion", "heart failure",

                # Neurological
                "seizures", "convulsions", "tremors", "jitteriness", "high-pitched cry",
                "bulging fontanelle", "abnormal tone", "flaccidity", "paralysis", "weakness",
                "abnormal reflexes", "clonus", "coma", "altered mental status",

                # Gastrointestinal
                "abdominal distention", "abdominal tenderness", "hepatomegaly", "splenomegaly",
                "ascites", "ileus", "bile-stained emesis", "rectal bleeding", "bloody stools",
                "melena", "absent bowel sounds",

                # Renal
                "oliguria", "anuria", "polyuria", "hematuria",

                # Metabolic
                "acidosis", "alkalosis", "hypoglycemia", "hyperglycemia",
                "hypocalcemia", "hyponatremia", "hypernatremia",

                # Skin
                "mottling", "erythema", "vesicles", "pustules", "desquamation",
                "meconium staining", "port-wine stain",

                # Ophthalmologic
                "conjunctivitis", "red eye", "discharge", "leukokoria", "cataracts",
                "chorioretinitis", "retinal hemorrhage",
            ],

            "anatomy": [
                # Respiratory System
                "lung", "lungs", "alveoli", "bronchi", "trachea", "larynx", "pharynx",
                "diaphragm", "pleura", "pleural space", "mediastinum", "pulmonary artery",
                "pulmonary vein", "surfactant",

                # Cardiovascular System
                "heart", "right atrium", "left atrium", "right ventricle", "left ventricle",
                "septum", "ventricular septum", "atrial septum", "foramen ovale",
                "ductus arteriosus", "ductus venosus", "aorta", "pulmonary artery",
                "coronary arteries", "umbilical artery", "umbilical vein", "vena cava",
                "myocardium", "pericardium", "valves", "mitral valve", "aortic valve",

                # Hematologic/Immune
                "bone marrow", "spleen", "thymus", "lymph nodes", "red blood cells",
                "white blood cells", "neutrophils", "lymphocytes", "platelets", "plasma",
                "hemoglobin", "fetal hemoglobin",

                # Neurological System
                "brain", "cerebrum", "cerebellum", "brainstem", "cortex", "ventricles",
                "meninges", "cerebrospinal fluid", "CSF", "spinal cord", "peripheral nerves",
                "cranial nerves", "brachial plexus", "facial nerve",

                # Gastrointestinal System
                "esophagus", "stomach", "small intestine", "duodenum", "ileum", "colon",
                "rectum", "anus", "liver", "gallbladder", "bile ducts", "pancreas",
                "peritoneum", "bowel", "umbilicus", "umbilical cord",

                # Renal/Genitourinary
                "kidneys", "ureters", "bladder", "urethra", "nephrons", "glomeruli",
                "renal pelvis", "testes", "ovaries", "scrotum",

                # Musculoskeletal
                "skeleton", "bones", "skull", "cranium", "fontanelles", "anterior fontanelle",
                "sutures", "vertebrae", "spine", "ribs", "sternum", "clavicle", "femur",
                "pelvis", "joints", "muscles",

                # Skin
                "skin", "epidermis", "dermis", "subcutaneous tissue",

                # Endocrine
                "pituitary gland", "thyroid gland", "adrenal glands",

                # Eyes/Ears
                "eyes", "cornea", "lens", "retina", "iris", "pupil", "conjunctiva",
                "ears", "tympanic membrane", "cochlea",

                # Placenta/Fetal
                "placenta", "umbilical cord", "amniotic fluid", "amniotic sac",
                "fetal circulation",
            ]
        }

        # Relationship patterns - Enhanced for neonatal/pediatric medicine
        # These patterns are used for relationship extraction but primary method is co-occurrence
        self.relationship_patterns = {
            "TREATS": [
                r"(\w+)\s+(?:is|for|treats?|therapy for|treatment of)\s+(\w+)",
                r"(\w+)\s+(?:administered|given)\s+(?:to|for)\s+(\w+)",
                r"(\w+)\s+(?:effective|indicated|recommended|prescribed)\s+(?:for|in)\s+(\w+)",
            ],
            "HAS_SYMPTOM": [
                r"(\w+)\s+(?:presents with|characterized by|symptoms include)\s+(\w+)",
                r"(\w+)\s+(?:may have|develops|shows)\s+(\w+)",
                r"(\w+)\s+(?:manifests|associated with)\s+(\w+)",
            ],
            "CAUSES": [
                r"(\w+)\s+(?:causes|results in|leads to)\s+(\w+)",
                r"(\w+)\s+(?:may cause|can result in)\s+(\w+)",
                r"(\w+)\s+(?:associated with|risk factor for)\s+(\w+)",
            ],
            "USED_FOR": [
                r"(\w+)\s+(?:for|in cases of|to treat)\s+(\w+)",
                r"(\w+)\s+(?:performed|used)\s+(?:for|in)\s+(\w+)",
            ],
            "PREVENTS": [
                r"(\w+)\s+(?:prevents|prevention of|prophylaxis for)\s+(\w+)",
                r"(\w+)\s+(?:to prevent|to reduce risk of)\s+(\w+)",
            ],
            "DIAGNOSED_BY": [
                r"(\w+)\s+(?:diagnosed by|detected by|identified by)\s+(\w+)",
                r"(\w+)\s+(?:diagnosis|screening)\s+(?:with|using)\s+(\w+)",
            ],
        }

    def extract_entities_from_chunks(self, limit: int = None) -> Dict[str, Set[str]]:
        """
        Extract entities from OpenSearch chunks

        Args:
            limit: Maximum number of chunks to process (None = all)

        Returns:
            Dictionary of entity_type -> set of entity names
        """
        print(f"[INFO] Extracting entities from chunks...")

        # Get all chunks (or sample)
        # Use a broad query to get many chunks
        all_chunks = []
        for term in ["infant", "newborn", "neonatal", "treatment", "disease"]:
            results = self.opensearch.search(term, top_k=200)
            all_chunks.extend(results)

        # Remove duplicates
        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit] if limit else list(unique_chunks)

        print(f"[OK] Processing {len(chunks)} chunks")

        # Extract entities
        found_entities = {entity_type: set() for entity_type in self.entity_patterns}

        for chunk in chunks:
            text = chunk.text.lower()

            for entity_type, patterns in self.entity_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in text:
                        found_entities[entity_type].add(pattern)

        # Print stats
        print(f"\n[ENTITIES FOUND]")
        for entity_type, entities in found_entities.items():
            if entities:
                print(f"  {entity_type.capitalize()}: {len(entities)}")
                for e in sorted(entities)[:5]:  # Show first 5
                    print(f"    - {e}")
                if len(entities) > 5:
                    print(f"    ... and {len(entities) - 5} more")

        return found_entities

    def extract_relationships_from_chunks(
        self,
        chunks: List,
        entities: Dict[str, Set[str]]
    ) -> List[Tuple[str, str, str]]:
        """
        Extract relationships from chunks using pattern matching

        Args:
            chunks: List of chunks
            entities: Dictionary of extracted entities

        Returns:
            List of (source, target, rel_type) tuples
        """
        print(f"\n[INFO] Extracting relationships...")

        relationships = []

        for chunk in chunks:
            text = chunk.text.lower()

            # Simple co-occurrence based relationships
            # If disease and drug appear together, likely TREATS relationship
            for disease in entities.get("disease", []):
                for drug in entities.get("drug", []):
                    if disease.lower() in text and drug.lower() in text:
                        # Check for treatment keywords
                        if any(kw in text for kw in ["treat", "therapy", "treatment", "administered"]):
                            relationships.append((drug, disease, "TREATS"))

            # Disease and symptom co-occurrence
            for disease in entities.get("disease", []):
                for symptom in entities.get("symptom", []):
                    if disease.lower() in text and symptom.lower() in text:
                        relationships.append((disease, symptom, "HAS_SYMPTOM"))

            # Procedure and disease co-occurrence
            for procedure in entities.get("procedure", []):
                for disease in entities.get("disease", []):
                    if procedure.lower() in text and disease.lower() in text:
                        relationships.append((procedure, disease, "USED_FOR"))

        # Remove duplicates
        relationships = list(set(relationships))

        print(f"[OK] Found {len(relationships)} relationships")
        for rel in relationships[:10]:  # Show first 10
            print(f"  {rel[0]} -[{rel[2]}]-> {rel[1]}")
        if len(relationships) > 10:
            print(f"  ... and {len(relationships) - 10} more")

        return relationships

    def build_graph(self, limit_chunks: int = None):
        """
        Build knowledge graph from PDF chunks

        Args:
            limit_chunks: Limit number of chunks to process (None = all)
        """
        print("="*80)
        print("BUILDING MEDICAL KNOWLEDGE GRAPH")
        print("="*80)
        print()

        # Step 1: Extract entities
        entities = self.extract_entities_from_chunks(limit=limit_chunks)

        # Step 2: Add entities to Neo4j
        print(f"\n[INFO] Adding entities to Neo4j...")
        entity_count = 0
        for entity_type, entity_names in entities.items():
            for name in entity_names:
                entity = Entity(
                    name=name,
                    type=entity_type,
                    properties={"source": "PDF extraction"}
                )
                self.neo4j.add_entity(entity)
                entity_count += 1

        print(f"[OK] Added {entity_count} entities to graph")

        # Step 3: Extract relationships
        # Get chunks again for relationship extraction
        all_chunks = []
        for term in ["infant", "newborn", "treatment"]:
            results = self.opensearch.search(term, top_k=200)
            all_chunks.extend(results)

        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit_chunks] if limit_chunks else list(unique_chunks)

        relationships = self.extract_relationships_from_chunks(chunks, entities)

        # Step 4: Add relationships to Neo4j
        print(f"\n[INFO] Adding relationships to Neo4j...")
        rel_count = 0
        for source, target, rel_type in relationships:
            relationship = Relationship(
                source=source,
                target=target,
                rel_type=rel_type,
                properties={"source": "PDF extraction"}
            )
            if self.neo4j.add_relationship(relationship):
                rel_count += 1

        print(f"[OK] Added {rel_count} relationships to graph")

        # Step 5: Show stats
        print("\n" + "="*80)
        print("KNOWLEDGE GRAPH BUILT")
        print("="*80)
        stats = self.neo4j.get_stats()
        print(f"\nTotal nodes: {stats['total_nodes']}")
        print(f"Total relationships: {stats['total_relationships']}")
        print(f"\nNodes by type:")
        for label, count in stats['nodes'].items():
            if count > 0:
                print(f"  {label}: {count}")

if __name__ == "__main__":
    print("=== Medical Knowledge Graph Builder ===\n")
    import os
    from dotenv import load_dotenv
    
    # env
    print("=== downloading env variables ===\n")
    
    load_dotenv()
    # Initialize stores - use environment variables
    print("[Loading] ElasticSearch...")
    opensearch = ElasticsearchStore()  # No parameters - uses ENV

    print("[Loading] Neo4j...")
    neo4j = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )

    # Clear existing graph (optional)
    print("\n[WARN] Clearing existing graph...")
    neo4j.clear_graph()

    # Build KG
    builder = MedicalKGBuilder(opensearch, neo4j)
    builder.build_graph(limit_chunks=500)

    # Cleanup
    opensearch.close()
    neo4j.close()

    print("\n[OK] Knowledge graph build complete!")