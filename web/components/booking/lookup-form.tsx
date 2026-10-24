"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Card } from "@/components/ui/primitives";

export function LookupForm() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string>();
  const normalized = code.replace(/[^a-z0-9]/gi, "").toUpperCase();

  return (
    <Card className="p-6">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (normalized.length !== 8) {
            setError("References are 8 letters and numbers, like K7Q2M9XD.");
            return;
          }
          router.push(`/booking/${normalized}`);
        }}
      >
        <Field label="Booking reference" error={error}>
          {(id) => (
            <Input
              id={id}
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                setError(undefined);
              }}
              placeholder="K7Q2M9XD"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              className="font-mono tracking-wider uppercase"
            />
          )}
        </Field>
        <Button type="submit">View booking</Button>
      </form>
    </Card>
  );
}
