#!/bin/bash
# LaTeX Compilation Script for RAG System Documentation

echo "=========================================="
echo "RAG System LaTeX Compilation Script"
echo "=========================================="
echo ""

# Check if pdflatex is installed
if ! command -v pdflatex &> /dev/null
then
    echo "❌ Error: pdflatex not found!"
    echo "Please install LaTeX:"
    echo "  Ubuntu/Debian: sudo apt-get install texlive-full"
    echo "  macOS: brew install --cask mactex"
    echo "  Windows: Install MiKTeX or TeX Live"
    exit 1
fi

echo "✅ pdflatex found"
echo ""

# Function to compile LaTeX document
compile_latex() {
    local file=$1
    local name=$(basename "$file" .tex)
    
    echo "📄 Compiling $file..."
    
    # First pass
    pdflatex -interaction=nonstopmode "$file" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        # Second pass for references
        pdflatex -interaction=nonstopmode "$file" > /dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            echo "✅ Successfully compiled: ${name}.pdf"
            
            # Clean up auxiliary files
            rm -f "${name}.aux" "${name}.log" "${name}.out" "${name}.toc" "${name}.nav" "${name}.snm"
            
            return 0
        else
            echo "❌ Error in second pass of $file"
            return 1
        fi
    else
        echo "❌ Error compiling $file"
        echo "Check ${name}.log for details"
        return 1
    fi
}

# Compile full paper
echo "=========================================="
echo "1. Compiling Full Academic Paper"
echo "=========================================="
compile_latex "RAG_SYSTEM_LATEX.tex"
echo ""

# Compile presentation
echo "=========================================="
echo "2. Compiling Presentation Slides"
echo "=========================================="
compile_latex "RAG_SYSTEM_PRESENTATION.tex"
echo ""

echo "=========================================="
echo "Compilation Complete!"
echo "=========================================="
echo ""
echo "Generated files:"
if [ -f "RAG_SYSTEM_LATEX.pdf" ]; then
    echo "  ✅ RAG_SYSTEM_LATEX.pdf (Full paper)"
fi
if [ -f "RAG_SYSTEM_PRESENTATION.pdf" ]; then
    echo "  ✅ RAG_SYSTEM_PRESENTATION.pdf (Slides)"
fi
echo ""
echo "To view:"
echo "  Linux: xdg-open RAG_SYSTEM_LATEX.pdf"
echo "  macOS: open RAG_SYSTEM_LATEX.pdf"
echo "  Windows: start RAG_SYSTEM_LATEX.pdf"
