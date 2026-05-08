@echo off
REM LaTeX Compilation Script for RAG System Documentation (Windows)

echo ==========================================
echo RAG System LaTeX Compilation Script
echo ==========================================
echo.

REM Check if pdflatex is installed
where pdflatex >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: pdflatex not found!
    echo Please install LaTeX:
    echo   Windows: Install MiKTeX from https://miktex.org/
    echo   Or TeX Live from https://www.tug.org/texlive/
    pause
    exit /b 1
)

echo pdflatex found
echo.

REM Compile full paper
echo ==========================================
echo 1. Compiling Full Academic Paper
echo ==========================================
echo Compiling RAG_SYSTEM_LATEX.tex...

pdflatex -interaction=nonstopmode RAG_SYSTEM_LATEX.tex >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    pdflatex -interaction=nonstopmode RAG_SYSTEM_LATEX.tex >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo Successfully compiled: RAG_SYSTEM_LATEX.pdf
        del RAG_SYSTEM_LATEX.aux RAG_SYSTEM_LATEX.log RAG_SYSTEM_LATEX.out RAG_SYSTEM_LATEX.toc >nul 2>&1
    ) else (
        echo Error in second pass
    )
) else (
    echo Error compiling RAG_SYSTEM_LATEX.tex
    echo Check RAG_SYSTEM_LATEX.log for details
)
echo.

REM Compile presentation
echo ==========================================
echo 2. Compiling Presentation Slides
echo ==========================================
echo Compiling RAG_SYSTEM_PRESENTATION.tex...

pdflatex -interaction=nonstopmode RAG_SYSTEM_PRESENTATION.tex >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    pdflatex -interaction=nonstopmode RAG_SYSTEM_PRESENTATION.tex >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo Successfully compiled: RAG_SYSTEM_PRESENTATION.pdf
        del RAG_SYSTEM_PRESENTATION.aux RAG_SYSTEM_PRESENTATION.log RAG_SYSTEM_PRESENTATION.out RAG_SYSTEM_PRESENTATION.toc RAG_SYSTEM_PRESENTATION.nav RAG_SYSTEM_PRESENTATION.snm >nul 2>&1
    ) else (
        echo Error in second pass
    )
) else (
    echo Error compiling RAG_SYSTEM_PRESENTATION.tex
    echo Check RAG_SYSTEM_PRESENTATION.log for details
)
echo.

echo ==========================================
echo Compilation Complete!
echo ==========================================
echo.
echo Generated files:
if exist RAG_SYSTEM_LATEX.pdf (
    echo   RAG_SYSTEM_LATEX.pdf (Full paper)
)
if exist RAG_SYSTEM_PRESENTATION.pdf (
    echo   RAG_SYSTEM_PRESENTATION.pdf (Slides)
)
echo.
echo To view: start RAG_SYSTEM_LATEX.pdf
echo.
pause
