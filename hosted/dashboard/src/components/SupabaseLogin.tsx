import { FormEvent, useState } from "react";
import { supabase } from "@/lib/supabase";
import { useSupabaseAuth } from "@/lib/useSupabaseAuth";

export default function SupabaseLogin() {
  const { signIn, error: authError } = useSupabaseAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      await signIn(email.trim(), password);
    } catch {
      setMessage("Sign in failed. Check the account details and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-12">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600">Veyra</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">Sign in to continue</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">Use your authorized Supabase account to access the hosted anomaly control plane.</p>
        <form onSubmit={submit} className="mt-7 space-y-4">
          <label className="block text-sm font-medium text-slate-700">
            Email
            <input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3 outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100" autoComplete="email" />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Password
            <input required type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3 outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100" autoComplete="current-password" />
          </label>
          {(message || authError) && <p role="alert" className="text-sm text-rose-600">{message ?? authError}</p>}
          <button disabled={busy} type="submit" className="h-11 w-full rounded-xl bg-violet-600 font-semibold text-white transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
