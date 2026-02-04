"""Message model for individual chat messages."""

from django.db import models


class Message(models.Model):
    """
    Individual message in a conversation.

    Stores both user messages and assistant responses,
    including structured data from workflow execution.
    """

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()

    # Workflow reference
    workflow_id = models.CharField(max_length=100, null=True, blank=True)
    workflow_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        null=True,
        blank=True
    )

    # Structured data from workflow
    protein_data = models.JSONField(
        null=True,
        blank=True,
        help_text='Sequence, UniProt info, structure source'
    )
    structure_data = models.JSONField(
        null=True,
        blank=True,
        help_text='PDB content, pLDDT, pocket info'
    )
    prediction_data = models.JSONField(
        null=True,
        blank=True,
        help_text='EC, kcat, Tm, stability predictions'
    )
    generation_data = models.JSONField(
        null=True,
        blank=True,
        help_text='Generated mutants, scores'
    )

    # Display options
    is_collapsed = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'synde_messages'
        ordering = ['created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        preview = self.content[:50]
        if len(self.content) > 50:
            preview += '...'
        return f"[{self.role}] {preview}"

    @property
    def has_structure(self):
        """Check if message has viewable structure."""
        if not self.structure_data:
            return False
        return bool(self.structure_data.get('pdb_data'))

    @property
    def has_predictions(self):
        """Check if message has prediction results."""
        return bool(self.prediction_data)

    @property
    def has_mutants(self):
        """Check if message has generated mutants."""
        if not self.generation_data:
            return False
        return bool(self.generation_data.get('validated_mutants'))

    def update_from_workflow(self, result: dict):
        """
        Update message from workflow result.

        Args:
            result: Workflow result state dictionary
        """
        # Extract protein data
        protein = result.get('protein', {})
        if protein:
            self.protein_data = {
                'sequence': protein.get('sequence'),
                'sequence_length': protein.get('sequence_length'),
                'uniprot_id': protein.get('uniprot_id'),
                'structure_source': protein.get('structure_source'),
            }

        # Extract structure data
        structure = result.get('structure', {})
        response = result.get('response', {})
        if protein.get('pdb_data') or structure:
            self.structure_data = {
                'pdb_data': protein.get('pdb_data') or response.get('wild_type_pdb'),
                'avg_plddt': protein.get('avg_plddt'),
                'pocket_residues': structure.get('pocket_residues') or response.get('pocket_residues'),
                'pocket_scores': structure.get('pocket_scores') or response.get('pocket_scores'),
            }

        # Extract prediction data
        if response.get('response_html'):
            self.prediction_data = {
                'response_html': response.get('response_html'),
                'natural_reply': response.get('natural_reply'),
            }

        # Extract generation data
        mutant = result.get('mutant', {})
        if mutant.get('validated_mutants'):
            self.generation_data = {
                'best_mutant': mutant.get('best_mutant'),
                'validated_mutants': mutant.get('validated_mutants'),
                'mutant_pdb': response.get('mutant_pdb'),
            }

        self.workflow_status = 'completed'
        self.save()
