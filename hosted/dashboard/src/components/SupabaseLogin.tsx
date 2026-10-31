import { FormEvent, useState } from "react";
import { supabase } from "@/lib/supabase";
import { useSupabaseAuth } from "@/lib/useSupabaseAuth";
import VeyraRadar from "@/components/VeyraRadar";

const proofPoints = ["Deterministic detection", "AI explains, never decides", "Every delivery audited"];

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

  const inputClass =
    "mt-2 h-11 w-full rounded-xl border-2 border-pine bg-white px-3 text-base font-medium text-pine outline-none placeholder:text-moss/60 focus:ring-4 focus:ring-pine/15";

  return (
    <main className="relative flex min-h-screen overflow-hidden bg-sea text-pine">
      {/* Brand panel (hidden on small screens) */}
      <section className="relative hidden flex-1 flex-col px-14 pt-12 lg:flex">
        <p className="text-2xl font-extrabold tracking-[0.22em]">VEYRA</p>
        <h1 className="mt-14 max-w-[520px] font-display text-6xl leading-[1.02]">Every alert, with its evidence.</h1>
        <p className="mt-5 max-w-[440px] text-lg leading-relaxed text-moss">
          Evidence-led monitoring for digital assets: detect, explain, escalate, and audit.
        </p>
        <ul className="mt-6 flex max-w-[520px] flex-wrap gap-2">
          {proofPoints.map((point) => (
            <li key={point} className="rounded-full border-2 border-pine bg-white px-3 py-1.5 font-mono text-xs font-medium uppercase tracking-wide">
              {point}
            </li>
          ))}
        </ul>
        <VeyraRadar size={520} className="pointer-events-none absolute -bottom-44 -left-28" />
      </section>

      {/* Sign-in card */}
      <section className="relative flex w-full items-center justify-center px-5 py-12 lg:w-[480px] lg:shrink-0 lg:pr-14">
        <div className="w-full max-w-md rounded-3xl border-2 border-pine bg-paper p-8 shadow-[8px_8px_0_var(--color-pine)]">
          <p className="text-xs font-extrabold uppercase tracking-[0.22em] lg:hidden">Veyra</p>
          <h2 className="mt-2 font-display text-4xl leading-tight lg:mt-0">Analyst sign in</h2>
          <p className="mt-2 text-sm leading-6 text-moss">Use your authorized account to access the hosted anomaly control plane.</p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            <label className="block font-mono text-xs font-medium uppercase tracking-[0.1em]">
              Email
              <input
                required
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className={inputClass}
                autoComplete="email"
                placeholder="name@company.com"
              />
            </label>
            <label className="block font-mono text-xs font-medium uppercase tracking-[0.1em]">
              Password
              <input
                required
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={inputClass}
                autoComplete="current-password"
                placeholder="Your password"
              />
            </label>
            {(message || authError) && (
              <p role="alert" className="text-sm font-medium text-red-700">
                {message ?? authError}
              </p>
            )}
            <button
              disabled={busy}
              type="submit"
              className="h-12 w-full rounded-xl border-2 border-pine bg-pine text-base font-bold text-mist transition hover:bg-moss disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.08em] text-moss">Sessions are verified by the API on every request.</p>
        </div>
      </section>
    </main>
  );
}