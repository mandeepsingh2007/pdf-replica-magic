import { redirect } from "next/navigation";

/** Portal marketing lives on the NE Graphics site; app entry is always login. */
export default function Home() {
  redirect("/login");
}
