"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { loginSchema, type LoginInput } from "@/lib/auth-schemas";
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

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  // Top-level error covers API failures (bad credentials, server down) —
  // anything that isn't a field-level validation issue.
  const [apiError, setApiError] = useState("");

  const form = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginInput): Promise<void> {
    setApiError("");
    try {
      await login(values.email, values.password);
      router.push("/dashboard");
    } catch (err) {
      setApiError(err instanceof ApiError ? err.detail : "Something went wrong");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Sign in</CardTitle>
          <CardDescription>Enter your credentials to continue</CardDescription>
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
                      <Input
                        type="password"
                        autoComplete="current-password"
                        {...field}
                      />
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
                {form.formState.isSubmitting ? "Signing in…" : "Sign in"}
              </Button>
              <p className="text-muted-foreground text-center text-sm">
                Don&apos;t have an account?{" "}
                <Link
                  href="/register"
                  className="text-primary underline underline-offset-4 hover:opacity-80"
                >
                  Create one
                </Link>
              </p>
            </CardFooter>
          </form>
        </Form>
      </Card>
    </main>
  );
}
