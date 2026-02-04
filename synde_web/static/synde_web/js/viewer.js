/**
 * 3D Protein Viewer using 3Dmol.js
 */

const Viewer = {
    modal: null,
    viewer: null,
    pdbData: null,
    isSpinning: false,

    init() {
        this.modal = document.getElementById('viewer-modal');
        if (!this.modal) return;

        // Set up close handlers
        this.modal.querySelector('.modal-close')?.addEventListener('click', () => this.hide());
        this.modal.querySelector('#viewer-modal-backdrop')?.addEventListener('click', () => this.hide());

        // Set up controls
        document.getElementById('viewer-style')?.addEventListener('change', (e) => {
            this.setStyle(e.target.value);
        });

        document.getElementById('viewer-color')?.addEventListener('change', (e) => {
            this.setColor(e.target.value);
        });

        document.getElementById('viewer-fullscreen')?.addEventListener('click', () => {
            this.toggleFullscreen();
        });

        document.getElementById('viewer-download')?.addEventListener('click', () => {
            this.downloadPDB();
        });

        document.getElementById('viewer-screenshot')?.addEventListener('click', () => {
            this.takeScreenshot();
        });

        document.getElementById('viewer-spin')?.addEventListener('click', () => {
            this.toggleSpin();
        });

        document.getElementById('viewer-reset')?.addEventListener('click', () => {
            this.resetView();
        });

        // Handle escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('active')) {
                this.hide();
            }
        });
    },

    show(pdbData, options = {}) {
        if (!this.modal || !pdbData) return;

        this.pdbData = pdbData;

        // Show modal
        this.modal.classList.add('active');
        this.modal.setAttribute('aria-hidden', 'false');

        // Initialize viewer
        setTimeout(() => {
            this.initViewer(pdbData, options);
        }, 100);
    },

    hide() {
        if (!this.modal) return;

        this.modal.classList.remove('active');
        this.modal.setAttribute('aria-hidden', 'true');

        // Clean up viewer
        if (this.viewer) {
            this.viewer.clear();
        }
        this.isSpinning = false;
    },

    initViewer(pdbData, options = {}) {
        const container = document.getElementById('viewer-container');
        if (!container) return;

        // Clear existing viewer
        container.innerHTML = '';

        // Create viewer
        this.viewer = $3Dmol.createViewer(container, {
            backgroundColor: 'white',
            antialias: true
        });

        // Add structure
        this.viewer.addModel(pdbData, 'pdb');

        // Set default style
        this.setStyle(options.style || 'cartoon');
        this.setColor(options.color || 'spectrum');

        // Center and zoom
        this.viewer.zoomTo();
        this.viewer.render();

        // Update info
        this.updateInfo();

        // Highlight pockets if provided
        if (options.pocketResidues) {
            this.highlightPockets(options.pocketResidues, options.pocketScores);
        }
    },

    setStyle(style) {
        if (!this.viewer) return;

        this.viewer.setStyle({}, {}); // Clear

        const styleMap = {
            'cartoon': { cartoon: { color: 'spectrum' } },
            'stick': { stick: {} },
            'sphere': { sphere: { scale: 0.3 } },
            'line': { line: {} },
            'surface': { surface: { opacity: 0.8 } }
        };

        this.viewer.setStyle({}, styleMap[style] || styleMap['cartoon']);
        this.viewer.render();
    },

    setColor(colorScheme) {
        if (!this.viewer) return;

        const currentStyle = document.getElementById('viewer-style')?.value || 'cartoon';
        this.viewer.setStyle({}, {});

        let colorSpec;
        switch (colorScheme) {
            case 'spectrum':
                colorSpec = { color: 'spectrum' };
                break;
            case 'chain':
                colorSpec = { colorscheme: 'chainHetatm' };
                break;
            case 'secondary':
                colorSpec = { colorscheme: 'ssJmol' };
                break;
            case 'residue':
                colorSpec = { colorscheme: 'amino' };
                break;
            case 'bfactor':
                colorSpec = { colorscheme: { prop: 'b', gradient: 'rwb', min: 0, max: 100 } };
                break;
            default:
                colorSpec = { color: 'spectrum' };
        }

        const styleMap = {
            'cartoon': { cartoon: colorSpec },
            'stick': { stick: colorSpec },
            'sphere': { sphere: { ...colorSpec, scale: 0.3 } },
            'line': { line: colorSpec },
            'surface': { surface: { ...colorSpec, opacity: 0.8 } }
        };

        this.viewer.setStyle({}, styleMap[currentStyle] || styleMap['cartoon']);
        this.viewer.render();
    },

    updateInfo() {
        if (!this.viewer) return;

        const model = this.viewer.getModel();
        if (!model) return;

        const atoms = model.selectedAtoms({});
        const residues = new Set();
        const chains = new Set();

        atoms.forEach(atom => {
            residues.add(`${atom.chain}:${atom.resi}`);
            chains.add(atom.chain);
        });

        const residuesEl = document.getElementById('viewer-residues');
        const chainsEl = document.getElementById('viewer-chains');

        if (residuesEl) residuesEl.textContent = residues.size;
        if (chainsEl) chainsEl.textContent = chains.size || 1;
    },

    highlightPockets(pocketResidues, pocketScores) {
        if (!this.viewer || !pocketResidues) return;

        const pocketContainer = document.getElementById('viewer-pockets');
        const pocketList = document.getElementById('pocket-list');

        if (pocketContainer && pocketList) {
            pocketContainer.style.display = 'block';
            pocketList.innerHTML = '';

            // Group residues by pocket
            const pockets = Array.isArray(pocketResidues[0]) ? pocketResidues : [pocketResidues];
            const scores = pocketScores || [];

            pockets.forEach((pocket, i) => {
                const btn = document.createElement('button');
                btn.className = 'btn btn-small btn-secondary';
                btn.textContent = `Pocket ${i + 1}${scores[i] ? ` (${scores[i].toFixed(2)})` : ''}`;
                btn.addEventListener('click', () => this.focusPocket(pocket));
                pocketList.appendChild(btn);
            });
        }

        // Highlight first pocket
        if (pocketResidues.length > 0) {
            const firstPocket = Array.isArray(pocketResidues[0]) ? pocketResidues[0] : pocketResidues;
            this.highlightResidues(firstPocket);
        }
    },

    highlightResidues(residues) {
        if (!this.viewer || !residues) return;

        // Highlight with spheres
        this.viewer.addStyle(
            { resi: residues },
            { sphere: { color: 'red', radius: 0.5 } }
        );
        this.viewer.render();
    },

    focusPocket(residues) {
        if (!this.viewer || !residues) return;

        // Reset style first
        this.setStyle(document.getElementById('viewer-style')?.value || 'cartoon');

        // Highlight pocket
        this.highlightResidues(residues);

        // Zoom to pocket
        this.viewer.zoomTo({ resi: residues });
        this.viewer.render();
    },

    toggleSpin() {
        if (!this.viewer) return;

        this.isSpinning = !this.isSpinning;
        this.viewer.spin(this.isSpinning);

        const btn = document.getElementById('viewer-spin');
        if (btn) {
            btn.classList.toggle('active', this.isSpinning);
        }
    },

    resetView() {
        if (!this.viewer) return;

        this.viewer.zoomTo();
        this.viewer.render();

        // Stop spinning
        if (this.isSpinning) {
            this.toggleSpin();
        }
    },

    toggleFullscreen() {
        const content = this.modal.querySelector('.modal-content');
        if (!content) return;

        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            content.requestFullscreen().catch(err => {
                console.error('Fullscreen error:', err);
            });
        }
    },

    downloadPDB() {
        if (!this.pdbData) return;

        const blob = new Blob([this.pdbData], { type: 'chemical/x-pdb' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'structure.pdb';
        a.click();
        URL.revokeObjectURL(url);
    },

    takeScreenshot() {
        if (!this.viewer) return;

        const canvas = this.viewer.getCanvas();
        if (!canvas) return;

        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'structure.png';
            a.click();
            URL.revokeObjectURL(url);
        });
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    Viewer.init();
});

window.Viewer = Viewer;
