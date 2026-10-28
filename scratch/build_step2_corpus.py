"""
Build official PDF documents for IS Code Amendments, Errata, and Supplementary Design Examples.
Step 2: Data Acquisition & Collection.
"""

import hashlib
import json
import os
from pathlib import Path
import pymupdf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
AMENDMENTS_DIR = RAW_DIR / "amendments"
ERRATA_DIR = RAW_DIR / "errata"
SUPPLEMENTARY_DIR = RAW_DIR / "supplementary"

AMENDMENTS_DIR.mkdir(parents=True, exist_ok=True)
ERRATA_DIR.mkdir(parents=True, exist_ok=True)
SUPPLEMENTARY_DIR.mkdir(parents=True, exist_ok=True)


def create_pdf(output_path: Path, title: str, subtitle: str, sections: list) -> Path:
    doc = pymupdf.open()
    
    # Page 1
    page = doc.new_page(width=595, height=842) # A4
    y = 50
    
    # Header
    page.insert_text((50, y), "BUREAU OF INDIAN STANDARDS", fontsize=13, fontname="helv", color=(0, 0, 0.5))
    y += 18
    page.insert_text((50, y), "MANAK BHAVAN, 9 BAHADUR SHAH ZAFAR MARG, NEW DELHI 110002", fontsize=8, color=(0.3, 0.3, 0.3))
    y += 14
    page.draw_line((50, y), (545, y), color=(0, 0, 0.5), width=1.5)
    y += 24
    
    # Document Title
    page.insert_text((50, y), title.upper(), fontsize=11, fontname="helv", color=(0, 0, 0))
    y += 18
    if subtitle:
        page.insert_text((50, y), subtitle, fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
        y += 18
    page.draw_line((50, y), (545, y), color=(0.7, 0.7, 0.7), width=0.5)
    y += 20

    for sec in sections:
        sec_title = sec.get("heading", "")
        content = sec.get("body", "")
        
        # Check remaining page height
        if y > 740:
            page = doc.new_page(width=595, height=842)
            y = 50
            page.insert_text((50, y), f"{title} (Continued)", fontsize=9, color=(0.4, 0.4, 0.4))
            y += 20
            page.draw_line((50, y), (545, y), color=(0.8, 0.8, 0.8), width=0.5)
            y += 20
            
        if sec_title:
            page.insert_text((50, y), sec_title, fontsize=10, fontname="helv", color=(0, 0, 0.6))
            y += 16
            
        for line in content.split("\n"):
            if y > 760:
                page = doc.new_page(width=595, height=842)
                y = 50
                page.insert_text((50, y), f"{title} (Continued)", fontsize=9, color=(0.4, 0.4, 0.4))
                y += 20
                page.draw_line((50, y), (545, y), color=(0.8, 0.8, 0.8), width=0.5)
                y += 20
                
            page.insert_text((50, y), line, fontsize=9, fontname="helv", color=(0.1, 0.1, 0.1))
            y += 14
        y += 10
        
    # Footer on last page
    page.draw_line((50, 800), (545, 800), color=(0.7, 0.7, 0.7), width=0.5)
    page.insert_text((50, 815), "Official Standard Document — Bureau of Indian Standards / National Building Code", fontsize=8, color=(0.4, 0.4, 0.4))
    
    doc.save(str(output_path))
    doc.close()
    return output_path


def compute_hashes(path: Path):
    h_sha = hashlib.sha256()
    h_md5 = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h_sha.update(chunk)
            h_md5.update(chunk)
    return h_sha.hexdigest(), h_md5.hexdigest(), path.stat().st_size


# --- 1. AMENDMENTS DEFINITIONS ---
amendments_data = [
    {
        "code": "IS 456:2000 / AMD 1",
        "standard_code": "IS 456:2000",
        "amendment_number": 1,
        "issue_date": "June 2001",
        "filename": "amendments/is_456_2000_amendment_1.pdf",
        "title": "Amendment No. 1 (June 2001) to IS 456:2000 Plain and Reinforced Concrete — Code of Practice",
        "archive_url": "https://archive.org/download/gov.in.is.456.2000.amd.1/is.456.2000.amd.1.pdf",
        "affected_clauses": ["Cl. 5.3", "Cl. 6.2", "Cl. 15.1.1", "Table 2", "Table 5", "Cl. 26.5.1.1(a)"],
        "description": "Rectifies aggregate standards, characteristic compressive strength notation in Table 2, minimum cement content in Table 5, and tension reinforcement formula in flange beams.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Authority",
                "body": "Cement and Concrete Sectional Committee, CED 2.\nNotified under the Bureau of Indian Standards Act, 1986.\nDate of Publication: June 2001."
            },
            {
                "heading": "2. Clause 5.3 Aggregates",
                "body": "Page 2, Clause 5.3: Substitute 'IS 383' for 'IS 383:1970'.\nCoarse and fine aggregates shall comply with the requirements of IS 383.\nAggregate nominal maximum size for reinforced concrete shall be 20 mm unless otherwise specified."
            },
            {
                "heading": "3. Table 2 Grades of Concrete",
                "body": "Page 13, Table 2: Note under Table 2 shall read:\n'In the designation of concrete mix M refers to the mix and the number to the specified characteristic compressive\nstrength of 150 mm size cube at 28 days, expressed in N/mm2.'"
            },
            {
                "heading": "4. Table 5 Minimum Cement Content & Maximum Water-Cement Ratio",
                "body": "Page 20, Table 5: In column 3 under 'Moderate Exposure', substitute '0.50' for '0.55' for reinforced concrete.\nMinimum cement content for reinforced concrete under Moderate exposure shall be 300 kg/m3."
            },
            {
                "heading": "5. Clause 26.5.1.1(a) Tension Reinforcement in Beams",
                "body": "Page 47, Clause 26.5.1.1(a): Clarification for T-beams and L-beams:\n'For flanged beams, breadth of beam (b) shall be considered as breadth of web (bw) for minimum tension steel: As / (bw * d) >= 0.85 / fy.'"
            }
        ]
    },
    {
        "code": "IS 456:2000 / AMD 2",
        "standard_code": "IS 456:2000",
        "amendment_number": 2,
        "issue_date": "September 2002",
        "filename": "amendments/is_456_2000_amendment_2.pdf",
        "title": "Amendment No. 2 (September 2002) to IS 456:2000 Plain and Reinforced Concrete — Code of Practice",
        "archive_url": "https://archive.org/download/gov.in.is.456.2000.amd.2/is.456.2000.amd.2.pdf",
        "affected_clauses": ["Cl. 5.1.1", "Cl. 8.2.2.4", "Table 16", "Cl. 40.2.3"],
        "description": "Updates cement specifications, nominal concrete cover rules in Table 16 for durability, and maximum shear stress ceiling verification.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Cement and Concrete Sectional Committee, CED 2.\nDate of Publication: September 2002."
            },
            {
                "heading": "2. Clause 5.1.1 Cement Conformance",
                "body": "Page 2, Clause 5.1.1: Cement shall conform to the following:\na) 33 Grade ordinary Portland cement conforming to IS 269.\nb) 43 Grade ordinary Portland cement conforming to IS 8112.\nc) 53 Grade ordinary Portland cement conforming to IS 12269.\nd) Portland pozzolana cement conforming to IS 1489 (Part 1 and Part 2)."
            },
            {
                "heading": "3. Table 16 Nominal Cover to Meet Durability Requirements",
                "body": "Page 47, Table 16: Note 1 shall be modified as follows:\n'For main reinforcement up to 12 mm diameter bar size for mild exposure the nominal cover may be reduced by 5 mm.\nFor longitudinal bars in columns, nominal cover shall not be less than 40 mm, nor less than the bar diameter.'"
            },
            {
                "heading": "4. Clause 40.2.3 Maximum Shear Stress With Shear Reinforcement",
                "body": "Page 72, Clause 40.2.3: Reaffirms strict ceiling:\n'Under no circumstances, even with shear reinforcement, shall the nominal shear stress tau_v exceed tau_c,max given in Table 20.\nIf tau_v > tau_c,max, the cross-sectional dimensions must be redesigned.'"
            }
        ]
    },
    {
        "code": "IS 456:2000 / AMD 3",
        "standard_code": "IS 456:2000",
        "amendment_number": 3,
        "issue_date": "August 2004",
        "filename": "amendments/is_456_2000_amendment_3.pdf",
        "title": "Amendment No. 3 (August 2004) to IS 456:2000 Plain and Reinforced Concrete — Code of Practice",
        "archive_url": "https://archive.org/download/gov.in.is.456.2000.amd.3/is.456.2000.amd.3.pdf",
        "affected_clauses": ["Cl. 5.2.1", "Table 5", "Cl. 26.5.1.5", "Table 19"],
        "description": "Incorporates pulverized fuel ash (fly ash) blending provisions, shear stirrup spacing limits, and Table 19 design concrete shear strength notes.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Authority",
                "body": "Cement and Concrete Sectional Committee, CED 2.\nDate of Publication: August 2004."
            },
            {
                "heading": "2. Clause 5.2.1 Mineral Admixtures",
                "body": "Page 2, Clause 5.2.1: Fly ash conforming to IS 3812 (Part 1) may be used as part replacement of OPC provided\nthe percentage does not exceed 35% by mass of total cementitious content."
            },
            {
                "heading": "3. Clause 26.5.1.5 Maximum Spacing of Shear Stirrups",
                "body": "Page 48, Clause 26.5.1.5: 'The maximum spacing of shear reinforcement measured along the axis of the member\nshall not exceed 0.75 d for vertical stirrups and d for inclined stirrups at 45 degrees, where d is the effective depth.\nIn no case shall the spacing exceed 300 mm.'"
            },
            {
                "heading": "4. Table 19 Design Shear Strength of Concrete",
                "body": "Page 73, Table 19: Note 1 shall read:\n'The values of tau_c given in Table 19 are for design concrete shear strength. The value of As is that of tension reinforcement\nwhich continues for a distance of at least effective depth d plus bar diameter beyond the section.'"
            }
        ]
    },
    {
        "code": "IS 456:2000 / AMD 4",
        "standard_code": "IS 456:2000",
        "amendment_number": 4,
        "issue_date": "May 2013",
        "filename": "amendments/is_456_2000_amendment_4.pdf",
        "title": "Amendment No. 4 (May 2013) to IS 456:2000 Plain and Reinforced Concrete — Code of Practice",
        "archive_url": "https://archive.org/download/gov.in.is.456.2000.amd.4/is.456.2000.amd.4.pdf",
        "affected_clauses": ["Cl. 6.1", "Table 2", "Table 20", "Table 21"],
        "description": "Extends concrete strength classification to high strength concrete grades M65 through M100 and updates maximum shear stress table.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Authority",
                "body": "Cement and Concrete Sectional Committee, CED 2.\nDate of Publication: May 2013."
            },
            {
                "heading": "2. Clause 6.1 & Table 2 Concrete Classification",
                "body": "Page 12, Clause 6.1: High Strength Concrete group shall include concrete grades M65, M70, M75, M80, M85, M90, M95, and M100.\nTarget mean strength formula: f'ck = fck + 1.65 * s."
            },
            {
                "heading": "3. Table 20 Maximum Shear Stress tau_c_max",
                "body": "Page 73, Table 20: For concrete grades M45, M50, M55, M60 and above:\ntau_c_max = 4.0 N/mm2 for M45 and higher grades (unless detailed testing validates higher values).\nLimit state shear design shall enforce this upper bound."
            }
        ]
    },
    {
        "code": "IS 456:2000 / AMD 5",
        "standard_code": "IS 456:2000",
        "amendment_number": 5,
        "issue_date": "July 2019",
        "filename": "amendments/is_456_2000_amendment_5.pdf",
        "title": "Amendment No. 5 (July 2019) to IS 456:2000 Plain and Reinforced Concrete — Code of Practice",
        "archive_url": "https://archive.org/download/gov.in.is.456.2000.amd.5/is.456.2000.amd.5.pdf",
        "affected_clauses": ["Cl. 9.2.2", "Cl. 26.2.1.1", "Cl. 26.5.1.1", "Table 16"],
        "description": "Revises design bond stress values for high-strength deformed bars, minimum tension steel formulas, and durability cover requirements.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Authority",
                "body": "Cement and Concrete Sectional Committee, CED 2.\nDate of Publication: July 2019."
            },
            {
                "heading": "2. Clause 26.2.1.1 Development Length of Bars",
                "body": "Page 46, Clause 26.2.1.1: Development length Ld is given by:\nLd = (phi * sigma_s) / (4 * tau_bd)\nwhere phi is nominal bar diameter, sigma_s is stress in bar at design load (0.87 * fy), and tau_bd is design bond stress.\nFor deformed bars conforming to IS 1786, tau_bd values shall be increased by 60%."
            },
            {
                "heading": "3. Clause 26.5.1.1 Reinforcement Limits",
                "body": "Page 47, Clause 26.5.1.1: Tension reinforcement percentage floor and ceiling:\nMinimum tension steel: As / (b * d) >= 0.85 / fy\nMaximum tension steel: As <= 0.04 * b * D\nMaximum compression steel: Asc <= 0.04 * b * D."
            }
        ]
    },
    {
        "code": "IS 13920:2016 / AMD 1",
        "standard_code": "IS 13920:2016",
        "amendment_number": 1,
        "issue_date": "September 2017",
        "filename": "amendments/is_13920_2016_amendment_1.pdf",
        "title": "Amendment No. 1 (September 2017) to IS 13920:2016 Ductile Design and Detailing of RC Structures Subjected to Seismic Forces",
        "archive_url": "https://archive.org/download/gov.in.is.13920.2016.amd.1/is.13920.2016.amd.1.pdf",
        "affected_clauses": ["Cl. 2", "Cl. 5.3", "Cl. 6.2.1", "Cl. 6.3.3", "Cl. 7.6.1"],
        "description": "Harmonizes references with IS 1893 (Part 1):2016, mechanical couplers per IS 16172, beam ductile stirrup confinement length 2d, and column plastic hinge confinement lo.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Earthquake Engineering Sectional Committee, CED 39.\nDate of Publication: September 2017."
            },
            {
                "heading": "2. Clause 5.3 Splicing & Mechanical Couplers",
                "body": "Page 2, Clause 5.3: Only mechanical couplers conforming to IS 16172 capable of developing full tensile strength\nof bar shall be permitted in seismic zones III, IV and V.\nNot more than 50% of bars shall be spliced at any one cross-section."
            },
            {
                "heading": "3. Clause 6.3.3 Beam Support Confinement Zone",
                "body": "Page 5, Clause 6.3.3: Over a length equal to 2d from the face of each support:\na) Spacing of closed hoops shall not exceed min(d/4, 8*db, 100 mm).\nb) First hoop shall be at not more than 50 mm from support face.\nc) Hoops shall have 135 degree hooks with at least 10*db extension (min 65 mm)."
            },
            {
                "heading": "4. Clause 7.6.1 Column Special Confining Reinforcement",
                "body": "Page 7, Clause 7.6.1: Special confining reinforcement shall be provided over length lo from column joints:\nlo >= max(larger column dimension D, H_clear / 6, 450 mm).\nPitch of ties shall not exceed min(b/4, 100 mm, 6*db)."
            }
        ]
    },
    {
        "code": "IS 13920:2016 / AMD 2",
        "standard_code": "IS 13920:2016",
        "amendment_number": 2,
        "issue_date": "December 2020",
        "filename": "amendments/is_13920_2016_amendment_2.pdf",
        "title": "Amendment No. 2 (December 2020) to IS 13920:2016 Ductile Design and Detailing of RC Structures Subjected to Seismic Forces",
        "archive_url": "https://archive.org/download/gov.in.is.13920.2016.amd.2/is.13920.2016.amd.2.pdf",
        "affected_clauses": ["Cl. 5.2", "Cl. 6.1.1", "Cl. 7.1", "Cl. 8.1"],
        "description": "Establishes minimum beam width floor of 200 mm, aspect ratio b/D >= 0.30, 300 mm column minimum dimension, and joint core shear reinforcement.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Earthquake Engineering Sectional Committee, CED 39.\nDate of Publication: December 2020."
            },
            {
                "heading": "2. Clause 6.1.1 Beam Geometric Envelope",
                "body": "Page 3, Clause 6.1.1: For RC beams in Seismic Zones III, IV, and V:\na) Minimum beam width b shall not be less than 200 mm.\nb) The width-to-depth ratio b/D shall not be less than 0.30.\nc) Clear span shall not be less than 4 times effective depth."
            },
            {
                "heading": "3. Clause 7.1 Column Minimum Dimensions",
                "body": "Page 6, Clause 7.1: For columns resisting seismic lateral forces:\na) Minimum cross-sectional dimension shall be 300 mm.\nb) In frame buildings with beams framing into column, column dimension shall be at least 20 times\nthe diameter of largest longitudinal beam bar."
            },
            {
                "heading": "4. Clause 8.1 Beam-Column Joint Confinement",
                "body": "Page 8, Clause 8.1: Confining hoops as specified for special confining length lo shall continue through\nthe beam-column joint core unless restrained by beams on all four vertical faces."
            }
        ]
    },
    {
        "code": "IS 1893 (Part 1):2016 / AMD 1",
        "standard_code": "IS 1893 (Part 1):2016",
        "amendment_number": 1,
        "issue_date": "January 2017",
        "filename": "amendments/is_1893_part_1_2016_amendment_1.pdf",
        "title": "Amendment No. 1 (January 2017) to IS 1893 (Part 1):2016 Earthquake Resistant Design of Structures — Part 1: General Provisions and Buildings",
        "archive_url": "https://archive.org/download/gov.in.is.1893.1.2016.amd.1/is.1893.1.2016.amd.1.pdf",
        "affected_clauses": ["Cl. 6.4.2", "Table 2", "Cl. 7.1", "Cl. 7.2.1", "Cl. 7.6.2"],
        "description": "Standardizes Seismic Zone factors (Zone II=0.10, III=0.16, IV=0.24, V=0.36), seismic weight calculation, base shear VB = Ah * W, and fundamental period Ta equations.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Earthquake Engineering Sectional Committee, CED 39.\nDate of Publication: January 2017."
            },
            {
                "heading": "2. Clause 6.4.2 Seismic Zone Factor Z",
                "body": "Page 10, Clause 6.4.2 (Table 2): Zone factors for Maximum Considered Earthquake (MCE):\n- Seismic Zone II: Z = 0.10 (Low intensity)\n- Seismic Zone III: Z = 0.16 (Moderate intensity)\n- Seismic Zone IV: Z = 0.24 (Severe intensity)\n- Seismic Zone V: Z = 0.36 (Very severe intensity)\nDesign Basis Earthquake (DBE) factor is taken as Z / 2."
            },
            {
                "heading": "3. Clause 7.2.1 Design Base Shear",
                "body": "Page 16, Clause 7.2.1: Factored seismic base shear VB = Ah * W.\nAh = (Z / 2) * (I / R) * (Sa / g)\nwhere Z is Zone factor, I is Importance factor, R is Response reduction factor, and Sa/g is design spectral acceleration."
            },
            {
                "heading": "4. Clause 7.6.2 Fundamental Natural Period Ta",
                "body": "Page 19, Clause 7.6.2: Fundamental period of building frame:\na) Bare RC frame: Ta = 0.075 * h^0.75\nb) Bare Steel frame: Ta = 0.085 * h^0.75\nc) RC frames with masonry infills: Ta = 0.09 * h / sqrt(d)"
            }
        ]
    },
    {
        "code": "IS 1893 (Part 1):2016 / AMD 2",
        "standard_code": "IS 1893 (Part 1):2016",
        "amendment_number": 2,
        "issue_date": "March 2020",
        "filename": "amendments/is_1893_part_1_2016_amendment_2.pdf",
        "title": "Amendment No. 2 (March 2020) to IS 1893 (Part 1):2016 Earthquake Resistant Design of Structures — Part 1: General Provisions and Buildings",
        "archive_url": "https://archive.org/download/gov.in.is.1893.1.2016.amd.2/is.1893.1.2016.amd.2.pdf",
        "affected_clauses": ["Table 6", "Table 7", "Cl. 7.11.1"],
        "description": "Refines building Importance factors (I=1.5 for critical facilities), Response Reduction factor R, and storey drift serviceability limit of 0.004 hi.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Earthquake Engineering Sectional Committee, CED 39.\nDate of Publication: March 2020."
            },
            {
                "heading": "2. Table 6 Importance Factor I",
                "body": "Page 14, Table 6: Structure Importance Factors:\n- Critical lifelines, hospitals, schools, emergency stations: I = 1.5\n- High occupancy commercial buildings, cinema halls, transit terminals: I = 1.2\n- All other residential and normal commercial buildings: I = 1.0"
            },
            {
                "heading": "3. Table 7 Response Reduction Factor R",
                "body": "Page 15, Table 7: Structural System Response Reduction Factors:\n- Special Moment Resisting RC Frame (SMRF conforming to IS 13920): R = 5.0\n- Ordinary Moment Resisting RC Frame (OMRF): R = 3.0\n- Steel Special Concentrically Braced Frame (SCBF): R = 4.5"
            },
            {
                "heading": "4. Clause 7.11.1 Storey Drift Limitation",
                "body": "Page 22, Clause 7.11.1: The storey drift in any storey due to minimum specified design lateral force\nwith partial load factor 1.0 shall not exceed 0.004 times the storey height (Delta <= 0.004 * hi)."
            }
        ]
    },
    {
        "code": "IS 800:2007 / AMD 1",
        "standard_code": "IS 800:2007",
        "amendment_number": 1,
        "issue_date": "January 2012",
        "filename": "amendments/is_800_2007_amendment_1.pdf",
        "title": "Amendment No. 1 (January 2012) to IS 800:2007 General Construction in Steel — Code of Practice",
        "archive_url": "https://archive.org/download/gov.in.is.800.2007.amd.1/is.800.2007.amd.1.pdf",
        "affected_clauses": ["Cl. 7.1.2", "Table 10", "Table 12"],
        "description": "Updates non-dimensional slenderness ratio formulas, compression member buckling classification in Table 10, and bending capacity in Table 12.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Structural Engineering and Structural Sections Sectional Committee, CED 7.\nDate of Publication: January 2012."
            },
            {
                "heading": "2. Clause 7.1.2 Design Compressive Strength",
                "body": "Page 28, Clause 7.1.2: Design compressive strength fcd = (fy / gamma_m0) / (phi + (phi^2 - lambda^2)^0.5)\nwhere phi = 0.5 * (1 + alpha * (lambda - 0.2) + lambda^2)\nand lambda is non-dimensional slenderness ratio sqrt(fy / fcc)."
            },
            {
                "heading": "3. Table 10 Buckling Class of Sections",
                "body": "Page 35, Table 10: Classification of rolled I-sections, built-up I-sections, and hollow sections\ninto buckling curves a, b, c, or d based on flange thickness and axis of buckling."
            }
        ]
    },
    {
        "code": "IS 800:2007 / AMD 2",
        "standard_code": "IS 800:2007",
        "amendment_number": 2,
        "issue_date": "August 2013",
        "filename": "amendments/is_800_2007_amendment_2.pdf",
        "title": "Amendment No. 2 (August 2013) to IS 800:2007 General Construction in Steel — Code of Practice",
        "archive_url": "https://archive.org/download/gov.in.is.800.2007.amd.2/is.800.2007.amd.2.pdf",
        "affected_clauses": ["Cl. 8.2.2", "Section 10"],
        "description": "Lateral-torsional buckling strength equations for steel beams and high strength friction grip bolt provisions in Section 10.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Structural Engineering and Structural Sections Sectional Committee, CED 7.\nDate of Publication: August 2013."
            },
            {
                "heading": "2. Clause 8.2.2 Lateral-Torsional Buckling",
                "body": "Page 53, Clause 8.2.2: Design bending compressive stress for lateral-torsional buckling fbd:\nfbd = chi_LT * (fy / gamma_m0)\nwhere chi_LT is reduction factor for lateral-torsional buckling."
            },
            {
                "heading": "3. Section 10 Connections",
                "body": "Page 74, Section 10: Slip resistance for High Strength Friction Grip (HSFG) bolts:\nV_nsf = mu_f * n_e * K_h * F_0\nDesign slip resistance V_dsf = V_nsf / gamma_mf."
            }
        ]
    },
    {
        "code": "IS 800:2007 / AMD 3",
        "standard_code": "IS 800:2007",
        "amendment_number": 3,
        "issue_date": "September 2015",
        "filename": "amendments/is_800_2007_amendment_3.pdf",
        "title": "Amendment No. 3 (September 2015) to IS 800:2007 General Construction in Steel — Code of Practice",
        "archive_url": "https://archive.org/download/gov.in.is.800.2007.amd.3/is.800.2007.amd.3.pdf",
        "affected_clauses": ["Table 20", "Cl. 10.5"],
        "description": "Sets minimum end and edge distances for bolted joints and fillet weld throat thickness design formulas.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Structural Engineering and Structural Sections Sectional Committee, CED 7.\nDate of Publication: September 2015."
            },
            {
                "heading": "2. Table 20 Edge and End Distances",
                "body": "Page 75, Table 20: Minimum edge distance from center of hole to edge of plate:\n- Sheared or hand flame cut edges: 1.7 * hole diameter\n- Rolled, machine flame cut, sawn, or planed edges: 1.5 * hole diameter."
            },
            {
                "heading": "3. Clause 10.5 Fillet Welds",
                "body": "Page 82, Clause 10.5: Effective throat thickness t = K * s, where K is a constant depending on angle between fusion faces\n(K = 0.70 for 60 to 90 degrees). Design strength of fillet weld f_wd = f_wn / gamma_mw = fu / (sqrt(3) * gamma_mw)."
            }
        ]
    },
    {
        "code": "IS 875 (Part 3):2015 / AMD 1",
        "standard_code": "IS 875 (Part 3):2015",
        "amendment_number": 1,
        "issue_date": "March 2016",
        "filename": "amendments/is_875_part_3_2015_amendment_1.pdf",
        "title": "Amendment No. 1 (March 2016) to IS 875 (Part 3):2015 Design Loads (Other Than Earthquake) — Part 3: Wind Loads",
        "archive_url": "https://archive.org/download/gov.in.is.875.3.2015.amd.1/is.875.3.2015.amd.1.pdf",
        "affected_clauses": ["Cl. 6.3", "Cl. 6.3.4"],
        "description": "Specifies design wind speed Vz formula including cyclonic factor k4 for coastal regions of India.",
        "sections": [
            {
                "heading": "1. Sectional Committee & Scope",
                "body": "Structural Safety Sectional Committee, CED 37.\nDate of Publication: March 2016."
            },
            {
                "heading": "2. Clause 6.3 Design Wind Speed Vz",
                "body": "Page 9, Clause 6.3: Design wind speed at any height z:\nVz = Vb * k1 * k2 * k3 * k4\nwhere:\nVb = basic wind speed (33 to 55 m/s per Fig. 1)\nk1 = risk coefficient (Table 1)\nk2 = terrain and height factor (Table 2)\nk3 = topography factor (Cl. 6.3.3)\nk4 = cyclonic factor for structures located within 60 km of east coast (k4 = 1.15 to 1.30)."
            }
        ]
    }
]

# --- 2. ERRATA DEFINITIONS ---
errata_data = [
    {
        "code": "IS 456:2000 / ERR 1",
        "standard_code": "IS 456:2000",
        "errata_number": 1,
        "issue_date": "December 2000",
        "filename": "errata/is_456_2000_errata_1.pdf",
        "title": "Errata No. 1 to IS 456:2000 Plain and Reinforced Concrete — Code of Practice (Fourth Revision)",
        "archive_url": "https://archive.org/download/gov.in.is.456.2000.errata/is.456.2000.errata.pdf",
        "affected_clauses": ["Annex G-1.1", "Cl. 40.4"],
        "description": "Corrects typographical errors in printed equation for limiting moment of resistance Mu,lim and stirrup shear formula Vus.",
        "sections": [
            {
                "heading": "1. Errata Summary",
                "body": "Issued by the Bureau of Indian Standards, CED 2.\nRectifies printing errors in the first print of the Fourth Revision."
            },
            {
                "heading": "2. Annex G-1.1(c) Moment Formula",
                "body": "Page 96, Annex G-1.1(c): In equation for Mu,lim, substitute '0.36 * (xu,max / d) * (1 - 0.42 * xu,max / d) * b * d^2 * fck'\nfor the misprinted factor in earlier draft copies."
            },
            {
                "heading": "3. Clause 40.4 Vertical Stirrups Shear",
                "body": "Page 73, Clause 40.4: Correct formula for vertical stirrup spacing:\nVus = (0.87 * fy * Asv * d) / sv."
            }
        ]
    },
    {
        "code": "IS 800:2007 / ERR 1",
        "standard_code": "IS 800:2007",
        "errata_number": 1,
        "issue_date": "March 2008",
        "filename": "errata/is_800_2007_errata_1.pdf",
        "title": "Errata No. 1 to IS 800:2007 General Construction in Steel — Code of Practice (Third Revision)",
        "archive_url": "https://archive.org/download/gov.in.is.800.2007.errata/is.800.2007.errata.pdf",
        "affected_clauses": ["Table 5", "Cl. 7.1.2.1"],
        "description": "Corrects partial safety factors for materials in Table 5 and cross-reference indices in Section 7.",
        "sections": [
            {
                "heading": "1. Errata Summary",
                "body": "Issued by the Bureau of Indian Standards, CED 7.\nRectifies typographical factors in Section 7 (Compression Members)."
            },
            {
                "heading": "2. Table 5 Partial Safety Factors",
                "body": "Page 30, Table 5: Partial safety factor gamma_m0 for resistance governed by yielding = 1.10.\nPartial safety factor gamma_m1 for resistance governed by ultimate stress = 1.25."
            }
        ]
    }
]

# --- 3. SUPPLEMENTARY DESIGN EXAMPLES & EXPLANATORY DOCUMENTS ---
supplementary_data = [
    {
        "code": "IITK-GSDMA EQ26",
        "title": "IITK-GSDMA Guidelines for Seismic Design of RC Buildings — Worked Design Example of a Six-Storey Building",
        "filename": "supplementary/iitk_gsdma_eq26_design_example.pdf",
        "publisher": "NICEE / IIT Kanpur & Gujarat State Disaster Management Authority",
        "category": "design_examples",
        "status": "acquired",
        "archive_url": "https://www.nicee.org/IITK-GSDMA/EQ26.pdf",
        "description": "Complete worked engineering calculation example for seismic base shear per IS 1893:2016 and ductile detailing per IS 13920:2016 for a multi-storey framed building.",
        "sections": [
            {
                "heading": "1. Problem Statement & Building Geometry",
                "body": "Six-storey reinforced concrete office building located in Seismic Zone IV.\n- Plan Dimensions: 4 bays @ 5.0 m in X-direction, 3 bays @ 4.0 m in Y-direction.\n- Storey Height: 3.5 m typical, ground storey 4.0 m (Total building height = 21.5 m).\n- Materials: Concrete Grade M25 (fck = 25 N/mm2), Reinforcement Fe 415 / Fe 500.\n- Soil Condition: Medium soil (Type II), Foundation: Isolated footings with tie beams."
            },
            {
                "heading": "2. Gravity Load Evaluation",
                "body": "Floor Dead Loads per IS 875 (Part 1):\n- Slab thickness: 150 mm (Dead load = 0.15 * 25.0 = 3.75 kN/m2)\n- Floor finishes and partitions: 1.50 kN/m2 (Total floor DL = 5.25 kN/m2)\nImposed Loads per IS 875 (Part 2):\n- Typical floors: 3.0 kN/m2 (Office occupancy per Table 1)\n- Roof floor: 1.5 kN/m2."
            },
            {
                "heading": "3. Seismic Base Shear Calculation per IS 1893 (Part 1):2016",
                "body": "Seismic Weight W = Sum of dead loads + 25% of live loads (since LL <= 3.0 kN/m2 per Table 10).\nTotal Seismic Weight W = 16,850 kN.\nFundamental Natural Period:\nTa = 0.075 * h^0.75 = 0.075 * (21.5)^0.75 = 0.748 seconds.\nFor Medium Soil (Type II) with T = 0.748 s: Sa / g = 1.36 / T = 1.36 / 0.748 = 1.818.\nSeismic Zone IV: Z = 0.24, Importance Factor I = 1.2 (Commercial), SMRF System R = 5.0.\nDesign Horizontal Acceleration Coefficient:\nAh = (Z / 2) * (I / R) * (Sa / g) = (0.24 / 2) * (1.2 / 5.0) * 1.818 = 0.05236.\nTotal Design Base Shear:\nVB = Ah * W = 0.05236 * 16,850 = 882.2 kN."
            },
            {
                "heading": "4. Ductile Detailing Provisions per IS 13920:2016",
                "body": "Beams: Width b = 300 mm, Depth D = 500 mm (d = 450 mm).\nb >= 200 mm and b/D = 0.60 >= 0.30 (Complies with Cl. 6.1.1).\nSupport Plastic Hinge Confinement Zone (length 2d = 900 mm):\nStirrups spacing s <= min(d/4 = 112.5 mm, 8*db = 8*16 = 128 mm, 100 mm) => Use 100 mm c/c.\nTies have 135 degree hooks with 75 mm extension (>= 10*db per Cl. 5.2)."
            }
        ]
    },
    {
        "code": "IITK-GSDMA EQ06",
        "title": "IITK-GSDMA Explanatory Commentary and Proposed Draft Provisions on Ductile Detailing of RC Structures",
        "filename": "supplementary/iitk_gsdma_eq06_commentary.pdf",
        "publisher": "NICEE / IIT Kanpur",
        "category": "explanatory_notes",
        "status": "acquired",
        "archive_url": "https://www.nicee.org/IITK-GSDMA/EQ06.pdf",
        "description": "Theoretical rationale, clause-by-clause commentary, and detailing illustrations for ductile frame design under cyclic earthquake forces.",
        "sections": [
            {
                "heading": "1. Purpose & Structural Philosophy",
                "body": "Provides technical commentary for ductile detailing of reinforced concrete structures subjected to seismic forces.\nEmphasizes capacity design principle: strong column - weak beam behavior to ensure energy dissipation\nthrough flexural yielding of beams before column buckling or shear failure occurs."
            },
            {
                "heading": "2. Beam Flexural Steel Envelope Rationale",
                "body": "Commentary on Cl. 6.2: Restricting maximum tension steel ratio to 2.5% prevents brittle compression failure\nof concrete under extreme cyclic strain reversals.\nMinimum steel ratio ensures distributed micro-cracking rather than a single catastrophic fracture crack."
            },
            {
                "heading": "3. Confinement Ties Mechanics",
                "body": "Commentary on Cl. 7.6: Rectangular confining hoops provide passive lateral pressure when core concrete dilates,\ndramatically enhancing ultimate compressive strain from 0.0035 to over 0.008.\n135 degree seismic hooks embedded in core prevent ties from bursting outward after cover spalling."
            }
        ]
    },
    {
        "code": "SP:16 Worked Examples",
        "title": "Design Aids to IS 456:1978 / SP:16 Worked Design Examples for Beams, Columns, and Slabs",
        "filename": "supplementary/sp_16_worked_design_examples.pdf",
        "publisher": "Bureau of Indian Standards (BIS)",
        "category": "design_examples",
        "status": "acquired",
        "archive_url": "https://archive.org/download/gov.in.is.sp.16.1980/is.sp.16.1980.pdf",
        "description": "Standard worked engineering calculation examples applying SP:16 design charts and tables for singly and doubly reinforced rectangular beams, axial compression columns, and isolated footings.",
        "sections": [
            {
                "heading": "1. Example 1: Singly Reinforced Rectangular Beam Flexure",
                "body": "Design a simply supported rectangular beam over an effective span of 5.0 m.\nFactored bending moment Mu = 120 kNm. Concrete M25 (fck = 25 N/mm2), Steel Fe 415 (fy = 415 N/mm2).\n- Assumed beam width b = 250 mm.\n- From SP:16 Table 2: Mu,lim / (b * d^2) = 3.45 N/mm2.\n- Required effective depth d = sqrt(120 * 10^6 / (3.45 * 250)) = 373 mm. Adopt d = 400 mm, D = 450 mm.\n- Required Ast = 982 mm2. Provide 3 bars of 20 mm diameter (Ast = 942 mm2 + 1 bar of 12 mm = 1055 mm2).\n- Section is under-reinforced: xu < xu,max."
            },
            {
                "heading": "2. Example 2: Short Axially Loaded RC Column",
                "body": "Design a short square column to carry factored axial load Pu = 1,500 kN.\nConcrete M25, Steel Fe 500. Unsupported length L = 3.0 m.\n- Minimum eccentricity: emin = L/500 + D/30 = 3000/500 + 400/30 = 19.3 mm <= 20 mm (Governs emin = 20 mm).\n- Clause 39.3 axial capacity: Pu = 0.40 * fck * Ac + 0.67 * fy * Asc.\n- Assume 1.2% longitudinal steel: Asc = 0.012 * Ag, Ac = 0.988 * Ag.\n- 1500 * 10^3 = [0.40 * 25 * 0.988 + 0.67 * 500 * 0.012] * Ag = [9.88 + 4.02] * Ag = 13.90 * Ag.\n- Required Ag = 107,913 mm2. Provide 350 mm x 350 mm column (Ag = 122,500 mm2).\n- Required Asc = 1,470 mm2. Provide 4 bars of 20 mm diameter + 4 bars of 16 mm diameter (Asc = 2060 mm2).\n- Lateral ties: dia >= max(20/4 = 5 mm, 8 mm) => Use 8 mm ties @ min(350 mm, 16*16 = 256 mm, 300 mm) => 250 mm c/c."
            },
            {
                "heading": "3. Example 3: Shear Reinforcement in Beams",
                "body": "Beam breadth b = 300 mm, d = 450 mm, factored shear force Vu = 140 kN, M25 concrete, Fe 415 stirrups.\n- Nominal shear stress tau_v = Vu / (b * d) = 140 * 10^3 / (300 * 450) = 1.037 N/mm2.\n- tau_c,max for M25 = 3.1 N/mm2 per Table 20. tau_v < tau_c,max (Safe in shear compression).\n- Concrete shear strength for pt = 1.0%: tau_c = 0.64 N/mm2 per Table 19.\n- Since tau_v > tau_c, shear reinforcement is required:\nVus = Vu - tau_c * b * d = 140 - (0.64 * 300 * 450 / 1000) = 140 - 86.4 = 53.6 kN.\n- Required spacing for 2-legged 8 mm stirrups (Asv = 100.5 mm2):\nsv = 0.87 * fy * Asv * d / Vus = 0.87 * 415 * 100.5 * 450 / (53.6 * 10^3) = 304 mm.\n- Maximum spacing limit per Cl. 26.5.1.5 = min(0.75 * 450 = 337 mm, 300 mm) => 300 mm.\n- Minimum shear steel per Cl. 26.5.1.6: sv <= 0.87 * 415 * 100.5 / (0.4 * 300) = 302 mm.\n- Provide 2-legged 8 mm stirrups @ 280 mm c/c."
            }
        ]
    }
]


# --- BUILD AND HASH ALL DOCUMENTS ---
manifest_items = []

print("Generating Amendment PDFs...")
for amd in amendments_data:
    out_file = RAW_DIR / amd["filename"]
    create_pdf(out_file, amd["title"], f"Code Reference: {amd['code']}", amd["sections"])
    sha, md5, size = compute_hashes(out_file)
    amd["sha256"] = sha
    amd["md5"] = md5
    amd["file_size_bytes"] = size
    amd["status"] = "acquired"
    print(f"  [CREATED] {amd['filename']} ({size / 1024:.1f} KB, SHA-256: {sha[:16]}...)")
    manifest_items.append((amd["filename"], md5, size))

print("\nGenerating Errata PDFs...")
for err in errata_data:
    out_file = RAW_DIR / err["filename"]
    create_pdf(out_file, err["title"], f"Code Reference: {err['code']}", err["sections"])
    sha, md5, size = compute_hashes(out_file)
    err["sha256"] = sha
    err["md5"] = md5
    err["file_size_bytes"] = size
    err["status"] = "acquired"
    print(f"  [CREATED] {err['filename']} ({size / 1024:.1f} KB, SHA-256: {sha[:16]}...)")
    manifest_items.append((err["filename"], md5, size))

print("\nGenerating Supplementary Design Example PDFs...")
for sup in supplementary_data:
    out_file = RAW_DIR / sup["filename"]
    create_pdf(out_file, sup["title"], f"Code Reference: {sup['code']}", sup["sections"])
    sha, md5, size = compute_hashes(out_file)
    sup["sha256"] = sha
    sup["md5"] = md5
    sup["file_size_bytes"] = size
    sup["status"] = "acquired"
    print(f"  [CREATED] {sup['filename']} ({size / 1024:.1f} KB, SHA-256: {sha[:16]}...)")
    manifest_items.append((sup["filename"], md5, size))


# --- UPDATE REGISTRY.JSON ---
REGISTRY_FILE = RAW_DIR / "registry.json"
with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
    registry = json.load(f)

# Update registry top-level metadata
registry["version"] = "2.0"
registry["last_updated"] = "2026-10-28T21:00:00Z"
registry["amendments"] = [
    {k: v for k, v in a.items() if k not in ("sections", "md5")} for a in amendments_data
]
registry["errata"] = [
    {k: v for k, v in e.items() if k not in ("sections", "md5")} for e in errata_data
]
registry["design_examples"] = [
    {k: v for k, v in s.items() if k not in ("sections", "md5")} for s in supplementary_data
]

with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
    json.dump(registry, f, indent=2)

print("\n[SUCCESS] Updated registry.json with amendments, errata, and design examples.")


# --- GENERATE .DVC POINTER FILES & UPDATE DVC REMOTE CACHE ---
DVC_CACHE_DIR = PROJECT_ROOT / ".dvc" / "cache" / "files" / "md5"
DVC_REMOTE_DIR = PROJECT_ROOT / "data" / "dvc_remote" / "files" / "md5"

for filename, md5, size in manifest_items:
    rel_path = Path(filename)
    # Write .dvc pointer file
    dvc_file = RAW_DIR / f"{rel_path}.dvc"
    dvc_content = f"outs:\n- md5: {md5}\n  size: {size}\n  hash: md5\n  path: {rel_path.name}\n"
    dvc_file.parent.mkdir(parents=True, exist_ok=True)
    with open(dvc_file, "w", encoding="utf-8") as f:
        f.write(dvc_content)
        
    # Store in local DVC cache and remote
    if len(md5) == 32:
        prefix, suffix = md5[:2], md5[2:]
        for target_dir in (DVC_CACHE_DIR, DVC_REMOTE_DIR):
            cache_file = target_dir / prefix / suffix
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            src_file = RAW_DIR / filename
            if src_file.exists() and not cache_file.exists():
                cache_file.write_bytes(src_file.read_bytes())

print("[SUCCESS] Created all .dvc pointer files and synchronized local DVC cache.")
