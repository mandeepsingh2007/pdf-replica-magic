export type SemesterBook = {
  id: string;
  subject: string;
  entry: string;
};

export type SemesterGroup = {
  id: string;
  label: string;
  books: SemesterBook[];
};

export type SemesterClass = {
  id: string;
  label: string;
  semesters: SemesterGroup[];
};

const CLASS1_SEM1: SemesterBook[] = [
  { id: "01", subject: "Computer", entry: "flipbook.html" },
  { id: "02", subject: "General Knowledge", entry: "index.html" },
  { id: "03", subject: "Mathematics", entry: "index.html" },
  { id: "04", subject: "English", entry: "index.html" },
  { id: "05", subject: "Environmental Studies", entry: "index.html" },
];

function semesterBooks(
  classId: string,
  semId: string,
  entries: { computer: string; gk: string; math: string; english: string; evs: string }
): SemesterBook[] {
  const prefix = `c${classId}s${semId}`;
  return [
    { id: `${prefix}-computer`, subject: "Computer", entry: entries.computer },
    { id: `${prefix}-gk`, subject: "General Knowledge", entry: entries.gk },
    { id: `${prefix}-math`, subject: "Mathematics", entry: entries.math },
    { id: `${prefix}-english`, subject: "English", entry: entries.english },
    { id: `${prefix}-evs`, subject: "Environmental Studies", entry: entries.evs },
  ];
}

export const SEMESTER_CLASSES: SemesterClass[] = [
  {
    id: "1",
    label: "Class 1",
    semesters: [
      { id: "1", label: "Semester 1", books: CLASS1_SEM1 },
      {
        id: "2",
        label: "Semester 2",
        books: semesterBooks("1", "2", {
          computer: "Computer Class1 Sem2.html",
          gk: "GK Class1 Sem2.html",
          math: "Math Class1 Sem2.html",
          english: "English Class1 Sem2.html",
          evs: "EVS Class1 Sem2.html",
        }),
      },
    ],
  },
  {
    id: "2",
    label: "Class 2",
    semesters: [
      {
        id: "1",
        label: "Semester 1",
        books: semesterBooks("2", "1", {
          computer: "Computer Class2 Sem1.html",
          gk: "GK Class2 Sem1.html",
          math: "Math Class2 Sem1.html",
          english: "English Class2 Sem1.html",
          evs: "EVS Class2 Sem1.html",
        }),
      },
      {
        id: "2",
        label: "Semester 2",
        books: semesterBooks("2", "2", {
          computer: "Computer Class2 Sem2.html",
          gk: "GK Class2 Sem2.html",
          math: "Maths Class2 Sem2.html",
          english: "English Class2 Sem2.html",
          evs: "EVS Class2 Sem2.html",
        }),
      },
    ],
  },
];

export function findSemesterBook(id: string) {
  for (const cls of SEMESTER_CLASSES) {
    for (const sem of cls.semesters) {
      const book = sem.books.find((b) => b.id === id);
      if (book) return { cls, sem, book };
    }
  }
  return null;
}
