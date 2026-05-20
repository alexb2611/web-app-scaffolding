"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { registerSchema, type RegisterInput } from "@/lib/auth-schemas";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

export default function RegisterPage() {
  const router = useRouter();
  const { register: registerUser } = useAuth();
  const [apiError, setApiError] = useState("");

  const form = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    mode: "onTouched",
    defaultValues: { email: "", password: "", full_name: "" },
  });

  async function onSubmit(values: RegisterInput): Promise<void> {
    setApiError("");
    try {
      // Coerce empty `full_name` to undefined so we don't POST an empty
      // string for an unspecified field.
      const fullName = values.full_name?.trim() || undefined;
      await registerUser(values.email, values.password, fullName);
      router.push("/dashboard");
    } catch (err) {
      setApiError(err instanceof ApiError ? err.detail : "Something went wrong");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Create account</CardTitle>
          <CardDescription>Sign up to get started</CardDescription>
        </CardHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
            <CardContent className="space-y-4">
              {apiError && (
                <div
                  role="alert"
                  className="bg-destructive/10 text-destructive rounded-md px-4 py-3 text-sm"
                >
                  {apiError}
                </div>
              )}

              <FormField
                control={form.control}
                name="full_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Full name{" "}
                      <span className="text-muted-foreground font-normal">
                        (optional)
                      </span>
                    </FormLabel>
                    <FormControl>
                      <Input type="text" autoComplete="name" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        autoComplete="email"
                        placeholder="you@example.com"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="new-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>

            <CardFooter className="flex flex-col gap-4">
              <Button
                type="submit"
                className="w-full"
                disabled={form.formState.isSubmitting}
              >
                {form.formState.isSubmitting ? "Creating account…" : "Create account"}
              </Button>
              <p className="text-muted-foreground text-center text-sm">
                Already have an account?{" "}
                <Link
                  href="/login"
                  className="text-primary underline underline-offset-4 hover:opacity-80"
                >
                  Sign in
                </Link>
              </p>
            </CardFooter>
          </form>
        </Form>
      </Card>
    </main>
  );
}
