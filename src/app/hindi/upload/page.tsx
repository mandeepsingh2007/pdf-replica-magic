import SubjectSelector, { HINDI_FORMAT_OPTIONS } from "@/components/SubjectSelector";
import { fetchSubjectsOnServer } from "@/lib/server-api";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

function hideHindiClass1(subjects: Awaited<ReturnType<typeof fetchSubjectsOnServer>>["subjects"]) {
  // Frontend-only: keep Hindi-1 in backend/DB, hide the Class 1 card on the portal.
  return subjects.filter((s) => s.name !== "Hindi-1");
}

export default async function HindiUploadPage() {
  const { subjects, error } = await fetchSubjectsOnServer("hindi");
  const visibleSubjects = hideHindiClass1(subjects);

  return (
    <div className="min-h-screen p-6 bg-background">
      <Link
        href="/hindi"
        className="inline-flex items-center mb-8 text-gray-400 transition-colors hover:text-white"
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        हिंदी पोर्टल
      </Link>

      <div className="flex flex-col items-center justify-center pt-10">
        <div className="mb-16 text-center">
          <h1 className="mb-4 text-4xl font-bold tracking-tight">
            हिंदी पाठमाला Test Generator
          </h1>
          <p className="max-w-xl mx-auto text-lg text-gray-400">
            कक्षा चुनें, पाठ चुनें, प्रश्न प्रकार चुनें — हर पाठ से नए प्रश्न बनेंगे।
          </p>
        </div>

        <SubjectSelector
          initialSubjects={visibleSubjects}
          initialLoadError={error ?? undefined}
          formatOptions={HINDI_FORMAT_OPTIONS}
          subjectsTrack="hindi"
          testBasePath="/test"
        />
      </div>
    </div>
  );
}
