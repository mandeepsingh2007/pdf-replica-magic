import SubjectSelector from "@/components/SubjectSelector";
import { fetchSubjectsOnServer } from "@/lib/server-api";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default async function UploadPage() {
  const { subjects, error } = await fetchSubjectsOnServer("english");

  return (
    <div className="min-h-screen bg-background p-6">
      <Link href="/home" className="inline-flex items-center text-gray-400 hover:text-white transition-colors mb-8">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to Home
      </Link>
      
      <div className="flex flex-col items-center justify-center pt-10">
        <div className="text-center mb-16">
          <h1 className="text-4xl font-bold tracking-tight mb-4">Class 1 Semester 1 Test Generator</h1>
          <p className="text-gray-400 max-w-xl mx-auto text-lg">
            Pick a subject, select chapters, choose formats — get 5 fresh questions per format every time.
          </p>
        </div>
        
        <SubjectSelector initialSubjects={subjects} initialLoadError={error ?? undefined} />
      </div>
    </div>
  );
}
