from app.services.descriptors import calculate_descriptors


def predict_toxicity(smiles: str):
    """
    Simple rule-based toxicity prediction using molecular descriptors.
    """

    descriptors = calculate_descriptors(smiles)

    score = 0

    if descriptors["MolecularWeight"] > 500:
        score += 2

    if descriptors["LogP"] > 5:
        score += 2

    if descriptors["TPSA"] > 140:
        score += 1

    if descriptors["HBD"] > 5:
        score += 1

    if descriptors["HBA"] > 10:
        score += 1

    if descriptors["RotatableBonds"] > 10:
        score += 1

    if score <= 2:
        risk = "Low"
    elif score <= 5:
        risk = "Medium"
    else:
        risk = "High"

    return {
        "Descriptors": descriptors,
        "ToxicityScore": score,
        "RiskLevel": risk
    }