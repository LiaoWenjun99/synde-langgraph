"""File upload views for PDB and FASTA files."""

import os
import re
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings


# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdb', '.fasta', '.fa', '.faa', '.fas', '.txt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def parse_fasta(content: str) -> dict:
    """
    Parse FASTA file content.

    Returns:
        Dict with sequences keyed by header
    """
    sequences = {}
    current_header = None
    current_seq = []

    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('>'):
            # Save previous sequence
            if current_header and current_seq:
                sequences[current_header] = ''.join(current_seq)

            # Start new sequence
            current_header = line[1:].split()[0]  # First word after >
            current_seq = []
        else:
            # Add to current sequence (remove non-amino acid chars)
            clean_seq = re.sub(r'[^ACDEFGHIKLMNPQRSTVWY]', '', line.upper())
            current_seq.append(clean_seq)

    # Save last sequence
    if current_header and current_seq:
        sequences[current_header] = ''.join(current_seq)

    return sequences


def validate_sequence(sequence: str) -> tuple:
    """
    Validate protein sequence.

    Returns:
        (is_valid, error_message)
    """
    if not sequence:
        return False, "Empty sequence"

    if len(sequence) < 10:
        return False, "Sequence too short (minimum 10 residues)"

    if len(sequence) > 2000:
        return False, "Sequence too long (maximum 2000 residues)"

    # Check for valid amino acids
    valid_aas = set('ACDEFGHIKLMNPQRSTVWY')
    invalid_chars = set(sequence.upper()) - valid_aas
    if invalid_chars:
        return False, f"Invalid amino acids: {', '.join(invalid_chars)}"

    return True, None


def validate_pdb(content: str) -> tuple:
    """
    Validate PDB file content.

    Returns:
        (is_valid, error_message, metadata)
    """
    if not content:
        return False, "Empty file", {}

    lines = content.strip().split('\n')

    # Check for ATOM records
    atom_count = sum(1 for line in lines if line.startswith('ATOM'))
    if atom_count == 0:
        return False, "No ATOM records found in PDB file", {}

    # Extract metadata
    metadata = {
        'atom_count': atom_count,
        'chains': set(),
        'residues': set(),
    }

    for line in lines:
        if line.startswith('ATOM') or line.startswith('HETATM'):
            if len(line) >= 22:
                chain = line[21]
                metadata['chains'].add(chain)
            if len(line) >= 26:
                resnum = line[22:26].strip()
                metadata['residues'].add(resnum)

    metadata['chains'] = list(metadata['chains'])
    metadata['residue_count'] = len(metadata['residues'])
    del metadata['residues']

    return True, None, metadata


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def upload_file(request):
    """
    Handle file upload (PDB or FASTA).

    Returns JSON with:
    - file_id: Unique identifier for the uploaded file
    - file_type: 'pdb' or 'fasta'
    - sequences: Dict of parsed sequences (for FASTA)
    - pdb_content: PDB file content (for PDB)
    - metadata: Additional file metadata
    """
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)

    uploaded_file = request.FILES['file']

    # Check file size
    if uploaded_file.size > MAX_FILE_SIZE:
        return JsonResponse({
            'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB'
        }, status=400)

    # Check extension
    filename = uploaded_file.name.lower()
    ext = os.path.splitext(filename)[1]

    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse({
            'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
        }, status=400)

    # Read file content
    try:
        content = uploaded_file.read().decode('utf-8')
    except UnicodeDecodeError:
        return JsonResponse({'error': 'Could not read file. Please ensure it is a text file.'}, status=400)

    # Generate unique file ID
    file_id = str(uuid.uuid4())[:8]

    # Process based on file type
    if ext == '.pdb':
        is_valid, error, metadata = validate_pdb(content)
        if not is_valid:
            return JsonResponse({'error': error}, status=400)

        # Save PDB file
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'pdb')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f'{file_id}.pdb')

        with open(file_path, 'w') as f:
            f.write(content)

        return JsonResponse({
            'file_id': file_id,
            'file_type': 'pdb',
            'file_path': file_path,
            'pdb_content': content,
            'metadata': metadata,
            'filename': uploaded_file.name,
        })

    else:  # FASTA
        sequences = parse_fasta(content)

        if not sequences:
            return JsonResponse({'error': 'No valid sequences found in FASTA file'}, status=400)

        # Validate sequences
        validated_sequences = {}
        errors = []

        for header, seq in sequences.items():
            is_valid, error = validate_sequence(seq)
            if is_valid:
                validated_sequences[header] = {
                    'sequence': seq,
                    'length': len(seq),
                }
            else:
                errors.append(f'{header}: {error}')

        if not validated_sequences:
            return JsonResponse({
                'error': 'No valid sequences found',
                'details': errors
            }, status=400)

        # Save FASTA file
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'fasta')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f'{file_id}.fasta')

        with open(file_path, 'w') as f:
            f.write(content)

        return JsonResponse({
            'file_id': file_id,
            'file_type': 'fasta',
            'file_path': file_path,
            'sequences': validated_sequences,
            'sequence_count': len(validated_sequences),
            'filename': uploaded_file.name,
            'warnings': errors if errors else None,
        })


@login_required
@require_http_methods(["GET"])
def get_uploaded_file(request, file_id):
    """Get information about an uploaded file."""
    # Check PDB files
    pdb_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'pdb', f'{file_id}.pdb')
    if os.path.exists(pdb_path):
        with open(pdb_path, 'r') as f:
            content = f.read()
        is_valid, error, metadata = validate_pdb(content)
        return JsonResponse({
            'file_id': file_id,
            'file_type': 'pdb',
            'file_path': pdb_path,
            'pdb_content': content,
            'metadata': metadata,
        })

    # Check FASTA files
    fasta_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'fasta', f'{file_id}.fasta')
    if os.path.exists(fasta_path):
        with open(fasta_path, 'r') as f:
            content = f.read()
        sequences = parse_fasta(content)
        return JsonResponse({
            'file_id': file_id,
            'file_type': 'fasta',
            'file_path': fasta_path,
            'sequences': {h: {'sequence': s, 'length': len(s)} for h, s in sequences.items()},
        })

    return JsonResponse({'error': 'File not found'}, status=404)
