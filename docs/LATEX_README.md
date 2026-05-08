# LaTeX Documentation for RAG System

This directory contains LaTeX documents explaining the advanced RAG system.

## Files

### 1. RAG_SYSTEM_LATEX.tex
**Full Academic Paper** - Comprehensive technical documentation

**Contents:**
- Abstract and introduction
- System architecture with diagrams
- All 10 innovations explained with algorithms
- Mathematical formulations
- Experimental results and tables
- Case studies
- Related work
- Implementation details
- API reference

**Compile:**
```bash
pdflatex RAG_SYSTEM_LATEX.tex
pdflatex RAG_SYSTEM_LATEX.tex  # Run twice for references
```

**Output:** ~20-25 page academic paper suitable for:
- Technical reports
- Research papers
- System documentation
- Academic submissions

### 2. RAG_SYSTEM_PRESENTATION.tex
**Beamer Presentation** - Slide deck for presentations

**Contents:**
- Introduction and motivation
- System architecture overview
- Key innovations (10 features)
- Performance results
- Demo examples

**Compile:**
```bash
pdflatex RAG_SYSTEM_PRESENTATION.tex
```

**Output:** ~15-20 slide presentation suitable for:
- Conference presentations
- Team meetings
- Stakeholder demos
- Academic defenses

## Prerequisites

### Required LaTeX Packages
```bash
# Ubuntu/Debian
sudo apt-get install texlive-full

# macOS
brew install --cask mactex

# Windows
# Download and install MiKTeX or TeX Live
```

### Required Packages (included in full distributions)
- amsmath, amssymb - Mathematical symbols
- graphicx - Graphics support
- hyperref - Hyperlinks
- listings - Code listings
- xcolor - Colors
- tikz - Diagrams
- algorithm, algorithmic - Algorithms
- booktabs - Professional tables
- beamer - Presentations

## Compilation Instructions

### Method 1: Command Line
```bash
# Full paper
cd docs/
pdflatex RAG_SYSTEM_LATEX.tex
pdflatex RAG_SYSTEM_LATEX.tex  # Second pass for references

# Presentation
pdflatex RAG_SYSTEM_PRESENTATION.tex
```

### Method 2: Online (Overleaf)
1. Go to https://www.overleaf.com
2. Create new project
3. Upload .tex file
4. Click "Recompile"

### Method 3: IDE
- **TeXstudio**: Open file → Build → Compile
- **TeXmaker**: Open file → Quick Build
- **VS Code**: Install LaTeX Workshop extension → Build

## Customization

### Change Title/Author
Edit these lines in the .tex file:
```latex
\title{Your Title Here}
\author{Your Name}
\date{\today}
```

### Add Your Logo
```latex
\usepackage{graphicx}
% In document:
\includegraphics[width=3cm]{your_logo.png}
```

### Change Colors (Presentation)
```latex
\usecolortheme{beaver}  % Red theme
\usecolortheme{dolphin} % Blue theme
\usecolortheme{crane}   % Orange theme
```

### Modify Algorithms
```latex
\begin{algorithm}
\caption{Your Algorithm}
\begin{algorithmic}
\STATE Your steps here
\end{algorithmic}
\end{algorithm}
```

## Key Sections Explained

### Abstract
Concise summary of the system (150-200 words)

### Introduction
- Motivation for the system
- Challenges in legal document retrieval
- Our contributions

### System Architecture
- Overall pipeline diagram
- Technology stack
- Component descriptions

### Phase 1-3 Innovations
- Each innovation explained with:
  - Problem statement
  - Solution approach
  - Algorithm/formula
  - Impact metrics

### Experimental Results
- Performance comparison tables
- Accuracy improvements
- Response time analysis
- Query type breakdown

### Case Studies
- Real-world examples
- Step-by-step processing
- Results and insights

### Implementation
- Code snippets
- Configuration details
- API reference

## Figures and Tables

### Adding Figures
```latex
\begin{figure}[h]
\centering
\includegraphics[width=0.8\textwidth]{figure.png}
\caption{Your caption}
\label{fig:yourlabel}
\end{figure}
```

### Adding Tables
```latex
\begin{table}[h]
\centering
\caption{Your caption}
\begin{tabular}{lcc}
\toprule
Header1 & Header2 & Header3 \\
\midrule
Data1 & Data2 & Data3 \\
\bottomrule
\end{tabular}
\end{table}
```

### TikZ Diagrams
```latex
\begin{tikzpicture}
\node[rectangle, draw] (a) {Node A};
\node[rectangle, draw, below of=a] (b) {Node B};
\draw[->] (a) -- (b);
\end{tikzpicture}
```

## Mathematical Formulas

### Inline Math
```latex
The accuracy is $98\%$ with $k=60$.
```

### Display Math
```latex
\begin{equation}
RRF(d) = \sum_{r} \frac{1}{k + rank_r(d)}
\end{equation}
```

### Aligned Equations
```latex
\begin{align}
x &= y + z \\
a &= b + c
\end{align}
```

## Code Listings

### Python Code
```latex
\begin{lstlisting}[language=Python]
def enhanced_retrieve(query):
    docs = retrieve(query)
    return rerank(docs)
\end{lstlisting}
```

### JSON
```latex
\begin{lstlisting}[language=json]
{
  "answer": "Response",
  "confidence": 0.95
}
\end{lstlisting}
```

## Bibliography

### Adding References
```latex
\begin{thebibliography}{99}
\bibitem{key}
Author. (Year). Title. Conference.
\end{thebibliography}
```

### Citing
```latex
As shown in \cite{key}, the system...
```

## Troubleshooting

### Common Errors

**Error: "File not found"**
- Ensure all image files are in the same directory
- Use relative paths

**Error: "Undefined control sequence"**
- Check package imports
- Verify command spelling

**Error: "Missing $ inserted"**
- Math mode issue
- Add $ around math expressions

**Error: "Package tikz not found"**
- Install missing package
- Use full LaTeX distribution

### Tips

1. **Compile twice** for references and table of contents
2. **Use \clearpage** to force page breaks
3. **Use \noindent** to remove paragraph indentation
4. **Use ~ for non-breaking space**: `Figure~\ref{fig:arch}`
5. **Use \textbf{} for bold**, \textit{} for italic

## Export Options

### PDF (Default)
```bash
pdflatex file.tex
```

### DVI → PS → PDF
```bash
latex file.tex
dvips file.dvi
ps2pdf file.ps
```

### With Bibliography
```bash
pdflatex file.tex
bibtex file
pdflatex file.tex
pdflatex file.tex
```

## Additional Resources

- **LaTeX Documentation**: https://www.latex-project.org/help/documentation/
- **Overleaf Tutorials**: https://www.overleaf.com/learn
- **TikZ Examples**: https://texample.net/tikz/
- **LaTeX Symbols**: https://www.ctan.org/pkg/comprehensive
- **Beamer Themes**: https://deic.uab.cat/~iblanes/beamer_gallery/

## License

These LaTeX documents are part of the Ministry Regulation project and follow the same MIT License.

## Support

For questions or issues:
- Check LaTeX error messages carefully
- Search on TeX StackExchange: https://tex.stackexchange.com/
- Consult package documentation: https://www.ctan.org/

---

**Note**: The LaTeX files are designed to be self-contained and compile without external dependencies (except standard LaTeX packages).
