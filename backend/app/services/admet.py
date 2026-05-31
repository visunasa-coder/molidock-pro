from fastapi import HTTPException, status

from app.schemas import ADMETPrediction


def predict_admet(smiles: str) -> ADMETPrediction:
    try:
        from rdkit import Chem
        from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RDKit is not installed. Install backend requirements with the RDKit package to enable ADMET descriptors.",
        ) from exc

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid SMILES string")

    molecular_weight = float(Descriptors.MolWt(mol))
    logp = float(Crippen.MolLogP(mol))
    hbd = int(Lipinski.NumHDonors(mol))
    hba = int(Lipinski.NumHAcceptors(mol))
    tpsa = float(rdMolDescriptors.CalcTPSA(mol))
    rotatable = int(Lipinski.NumRotatableBonds(mol))

    violations = sum(
        [
            molecular_weight > 500,
            logp > 5,
            hbd > 5,
            hba > 10,
        ]
    )

    if logp < 1.5 and tpsa > 80:
        soluble_signal = "high"
    elif logp <= 4.5 and tpsa <= 140:
        soluble_signal = "moderate"
    else:
        soluble_signal = "low"

    if violations == 0 and rotatable <= 10:
        oral_signal = "strong"
    elif violations <= 1:
        oral_signal = "moderate"
    else:
        oral_signal = "weak"

    notes = [
        "Descriptor-only screening signal, not a clinical or toxicology conclusion.",
        "Use validated ADMET/QSAR models and experimental data before commercial claims.",
    ]

    return ADMETPrediction(
        smiles=smiles,
        molecular_weight=round(molecular_weight, 3),
        logp=round(logp, 3),
        h_bond_donors=hbd,
        h_bond_acceptors=hba,
        tpsa=round(tpsa, 3),
        rotatable_bonds=rotatable,
        lipinski_violations=int(violations),
        soluble_signal=soluble_signal,
        oral_druglikeness_signal=oral_signal,
        notes=notes,
    )

