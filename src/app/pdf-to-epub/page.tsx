'use client';

import { useState } from 'react';
import Header from '@/components/Header';
import BackNav from '@/components/BackNav';
import { storage, db } from '@/lib/firebase/firebase';
import { ref, uploadBytesResumable } from 'firebase/storage';
import { doc, setDoc, onSnapshot } from 'firebase/firestore';

export default function PdfToEpub() {
    const [file, setFile] = useState<File | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'processing' | 'completed'>('idle');
    const [progress, setProgress] = useState(0);
    const [downloadUrl, setDownloadUrl] = useState<string>('');

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    };

    // Lógica real hacia Firebase
    const uploadToFirebase = async (file: File) => {
        setUploadStatus('uploading');
        setProgress(0);

        // Generar un ID único para la conversión
        const jobId = `job_${Date.now()}`;

        try {
            // 1. Crear el documento en Firestore para escuchar el progreso
            const jobRef = doc(db, 'epub_conversions', jobId);
            await setDoc(jobRef, {
                status: 'pending',
                progress: 0,
                fileName: file.name,
                createdAt: new Date().toISOString()
            });

            // 2. Escuchar cambios en Firestore EN TIEMPO REAL
            const unsubscribe = onSnapshot(jobRef, (docSnap) => {
                const data = docSnap.data();
                if (data) {
                    if (data.status === 'processing') {
                        setUploadStatus('processing');
                        setProgress(data.progress || 0);
                    } else if (data.status === 'completed') {
                        setUploadStatus('completed');
                        setProgress(100);
                        if (data.downloadUrl) {
                            setDownloadUrl(data.downloadUrl);
                        }
                        // Optional: trigger download automatically or set URL
                        // Para propósitos UI guardaremos la url en el estado o lo podemos obtener desde `data.downloadUrl`
                        unsubscribe();
                    } else if (data.status === 'error') {
                        alert('Ocurrió un error en la conversión.');
                        setUploadStatus('idle');
                        unsubscribe();
                    }
                }
            });

            // 3. Subir el PDF a Firebase Storage
            const storageRef = ref(storage, `pdf_uploads/${jobId}.pdf`);
            const uploadTask = uploadBytesResumable(storageRef, file);

            uploadTask.on('state_changed',
                (snapshot) => {
                    // Solo actualizamos la barrar visual de la subida,
                    // una vez subido la Cloud Function toma el control.
                    const uploadProgress = (snapshot.bytesTransferred / snapshot.totalBytes) * 100;
                    if (uploadProgress < 100) {
                        setProgress(uploadProgress / 2); // Subida es el primeros 50% virtual de la UX
                    }
                },
                (error) => {
                    console.error("Error al subir el archivo", error);
                    alert("Error al subir el archivo. Inténtalo de nuevo.");
                    setUploadStatus('idle');
                    unsubscribe();
                },
                () => {
                    // Subida completada
                    setUploadStatus('processing');
                }
            );

        } catch (error) {
            console.error(error);
            alert("Error al iniciar el proceso");
            setUploadStatus('idle');
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile && droppedFile.type === 'application/pdf') {
            setFile(droppedFile);
            uploadToFirebase(droppedFile);
        } else {
            alert('Por favor, sube un archivo PDF válido.');
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (selectedFile && selectedFile.type === 'application/pdf') {
            setFile(selectedFile);
            uploadToFirebase(selectedFile);
        }
    };

    const resetFlow = () => {
        setFile(null);
        setUploadStatus('idle');
        setProgress(0);
        setDownloadUrl('');
    };

    return (
        <div className="subpage-layout fade-in">
            <BackNav />
            <Header tagline="Herramientas In-House" mainText="PDF A EPUB" />

            <section className="content-body" style={{ marginTop: '3rem' }}>
                <p className="description" style={{ marginBottom: '2rem' }}>
                    Convierte tus documentos PDF en formato de lectura optimizado EPUB de manera sencilla.
                </p>

                {uploadStatus === 'idle' && (
                    <div
                        className={`upload-area ${isDragging ? 'dragging' : ''}`}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                    >
                        <div className="upload-icon">
                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="17 8 12 3 7 8"></polyline>
                                <line x1="12" y1="3" x2="12" y2="15"></line>
                            </svg>
                        </div>
                        <h3>Arrastra tu PDF aquí</h3>
                        <p>o</p>
                        <input
                            type="file"
                            id="pdf-upload"
                            accept=".pdf"
                            onChange={handleFileChange}
                            style={{ display: 'none' }}
                        />
                        <label htmlFor="pdf-upload" className="upload-btn">
                            Seleccionar Archivo
                        </label>
                    </div>
                )}

                {(uploadStatus === 'uploading' || uploadStatus === 'processing') && (
                    <div className="processing-area">
                        <div className="processing-header">
                            <h3 className="file-name">{file?.name}</h3>
                            <span className="status-text">
                                {uploadStatus === 'uploading' ? 'Subiendo...' : 'Convirtiendo a EPUB...'}
                            </span>
                        </div>

                        <div className="progress-bar-container">
                            <div
                                className={`progress-fill ${uploadStatus === 'processing' ? 'processing-pulse' : ''}`}
                                style={{ width: uploadStatus === 'processing' ? '100%' : `${progress}%` }}
                            ></div>
                        </div>

                        <p className="wait-message" style={{ marginTop: '1rem', color: 'var(--muted)', fontSize: '0.85rem' }}>
                            {uploadStatus === 'processing' ? 'Por favor espera. Este proceso puede tardar un momento dependiendo del tamaño del archivo.' : ''}
                        </p>
                    </div>
                )}

                {uploadStatus === 'completed' && (
                    <div className="completed-area">
                        <div className="success-icon">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                                <polyline points="22 4 12 14.01 9 11.01"></polyline>
                            </svg>
                        </div>
                        <h3>¡Conversión Completada!</h3>
                        <p className="success-text">Tu archivo {file?.name.replace('.pdf', '')}.epub está listo.</p>

                        <div className="action-buttons" style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
                            {downloadUrl ? (
                                <a href={downloadUrl} className="download-btn" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }} target="_blank" rel="noopener noreferrer">
                                    Descargar EPUB
                                </a>
                            ) : (
                                <button className="download-btn" disabled>
                                    Cargando enlace...
                                </button>
                            )}
                            <button className="secondary-btn" onClick={resetFlow}>
                                Convertir otro archivo
                            </button>
                        </div>
                    </div>
                )}
            </section>
        </div>
    );
}
