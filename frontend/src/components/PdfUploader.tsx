"use client";

import { useState, useRef } from "react";
import { UploadCloud, FileText, CheckCircle2, Loader2 } from "lucide-react";

export default function PdfUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [subjectId, setSubjectId] = useState<number>(1);
  const [isUploading, setIsUploading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "completed" | "failed">("idle");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const subjects = [
    { id: 1, name: "Science" },
    { id: 2, name: "Mathematics" },
    { id: 3, name: "SST" },
    { id: 4, name: "EVS" },
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setStatus("uploading");
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("subject_id", subjectId.toString());

    try {
      // Mocking API delay for UX
      await new Promise(r => setTimeout(r, 1000));
      
      // In real implementation:
      // const res = await fetch("http://localhost:8000/api/upload", { method: "POST", body: formData });
      // const data = await res.json();
      // setTaskId(data.task_id);
      
      // Mock Data
      setTaskId("mock-task-id-123");
      setStatus("processing");
      simulateProgress();
      
    } catch (error) {
      console.error(error);
      setStatus("failed");
    } finally {
      setIsUploading(false);
    }
  };

  const simulateProgress = () => {
    // This mocks the websocket connection
    const steps = [
      { p: 10, msg: "Parsing PDF Layout..." },
      { p: 30, msg: "Extracting Images & Tables..." },
      { p: 50, msg: "Vision AI Analyzing Images..." },
      { p: 70, msg: "Generating 150 Marks of Questions..." },
      { p: 90, msg: "Running ILP Math Optimization..." },
      { p: 100, msg: "Exact 50-Mark Test Assembled!" }
    ];
    
    let i = 0;
    const interval = setInterval(() => {
      if (i < steps.length) {
        setProgress(steps[i].p);
        setCurrentStep(steps[i].msg);
        if (steps[i].p === 100) {
          setStatus("completed");
          clearInterval(interval);
        }
        i++;
      }
    }, 2500); // Wait 2.5s between steps to simulate heavy backend
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-8 glass-card rounded-3xl">
      <h2 className="mb-6 text-2xl font-bold text-center">Generate Test Paper</h2>
      
      {/* Subject Selection */}
      <div className="grid grid-cols-2 gap-4 mb-8 sm:grid-cols-4">
        {subjects.map(sub => (
          <button
            key={sub.id}
            onClick={() => setSubjectId(sub.id)}
            disabled={status !== "idle"}
            className={`p-3 text-sm font-medium transition-all duration-200 border rounded-xl ${
              subjectId === sub.id 
                ? "bg-blue-600/20 border-blue-500 text-blue-400" 
                : "border-white/10 hover:bg-white/5 text-gray-400"
            } ${status !== "idle" && "opacity-50 cursor-not-allowed"}`}
          >
            {sub.name}
          </button>
        ))}
      </div>

      {status === "idle" || status === "uploading" ? (
        <div 
          className="relative flex flex-col items-center justify-center w-full h-64 border-2 border-dashed rounded-2xl border-white/20 bg-black/20 hover:bg-white/5 transition-colors cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
        >
          <input 
            type="file" 
            ref={fileInputRef}
            className="hidden" 
            accept=".pdf" 
            onChange={handleFileChange}
          />
          
          {file ? (
            <div className="flex flex-col items-center text-center">
              <FileText className="w-12 h-12 mb-3 text-blue-400" />
              <p className="font-semibold text-lg">{file.name}</p>
              <p className="text-sm text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              <button 
                onClick={(e) => { e.stopPropagation(); handleUpload(); }}
                className="mt-6 px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-lg font-medium transition-all"
              >
                {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Upload & Generate"}
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center text-gray-400">
              <UploadCloud className="w-12 h-12 mb-3 text-gray-500" />
              <p className="font-medium text-lg">Click or drag PDF to upload</p>
              <p className="text-sm mt-1">Maximum file size 50MB</p>
            </div>
          )}
        </div>
      ) : (
        <div className="w-full py-8 text-center">
          {status === "completed" ? (
             <div className="flex flex-col items-center animate-in fade-in zoom-in duration-500">
               <div className="w-20 h-20 mb-4 bg-green-500/20 text-green-500 flex items-center justify-center rounded-full">
                  <CheckCircle2 className="w-10 h-10" />
               </div>
               <h3 className="text-2xl font-bold mb-2">Test Assembled!</h3>
               <p className="text-gray-400 mb-8">Your exact 50-mark test is ready.</p>
               <button className="px-8 py-3 bg-white text-black font-semibold rounded-xl hover:bg-gray-200 transition-colors">
                  View Test Paper
               </button>
             </div>
          ) : (
            <div className="flex flex-col items-center w-full max-w-md mx-auto">
              <div className="w-16 h-16 mb-6">
                <Loader2 className="w-full h-full text-blue-500 animate-spin" />
              </div>
              <h3 className="text-xl font-semibold mb-2">{currentStep}</h3>
              <div className="w-full h-2 bg-white/10 rounded-full mt-6 overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all duration-500 ease-out"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
              <p className="text-right w-full mt-2 text-sm text-gray-400">{progress}%</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
