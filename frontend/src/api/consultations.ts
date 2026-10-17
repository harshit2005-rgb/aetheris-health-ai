import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "@/api/http";
import { ApiError, type Paginated } from "@/api/types";

/**
 * Consultation (EMR) API — typed hooks over `backend/app/api/v1/consultations.py`
 * (docs/modules/16-consultation.md §9). One note per visit, owned by the visit's
 * doctor; a finalized note is never edited, only added to.
 */

export type ConsultationStatus = "draft" | "finalized";

export interface Diagnosis {
  code: string | null;
  description: string;
}

/** Vital signs as stored. Decimals arrive as strings. */
export interface Vitals {
  bp_systolic?: number;
  bp_diastolic?: number;
  pulse?: number;
  temperature_c?: string;
  spo2?: number;
  respiratory_rate?: number;
  weight_kg?: string;
  height_cm?: string;
}

export interface ConsultationAddendum {
  id: string;
  text: string;
  added_by: string;
  added_at: string;
}

export interface ConsultationPrescription {
  id: string;
  status: string;
  prescribed_at: string;
  items: {
    medicine_name: string;
    dosage: string;
    frequency: string;
    duration_days: number | null;
    quantity: number;
  }[];
}

export interface ConsultationLabOrder {
  id: string;
  status: string;
  priority: string;
  ordered_at: string;
  tests: string[];
  has_abnormal: boolean;
}

export interface ConsultationSummary {
  id: string;
  appointment_id: string;
  patient_id: string;
  patient_name: string;
  patient_mrn: string;
  doctor_id: string;
  doctor_name: string;
  status: ConsultationStatus;
  visit_at: string;
  chief_complaint: string | null;
  diagnoses: Diagnosis[];
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Consultation extends ConsultationSummary {
  history: string | null;
  examination: string | null;
  plan: string | null;
  follow_up_date: string | null;
  vitals: Vitals | null;
  bmi: string | null;
  vitals_recorded_at: string | null;
  vitals_recorded_by: string | null;
  finalized_by: string | null;
  is_own: boolean;
  addenda: ConsultationAddendum[];
  prescriptions: ConsultationPrescription[];
  lab_orders: ConsultationLabOrder[];
}

/** The clinical sections a doctor writes. A field left out is unchanged. */
export interface ConsultationSections {
  chief_complaint?: string | null;
  history?: string | null;
  examination?: string | null;
  diagnoses?: Diagnosis[];
  plan?: string | null;
  follow_up_date?: string | null;
}

export const consultationKeys = {
  all: ["consultations"] as const,
  visit: (appointmentId: string) =>
    [...consultationKeys.all, "visit", appointmentId] as const,
  list: (params: Record<string, unknown>) =>
    [...consultationKeys.all, "list", params] as const,
};

/**
 * The note of one visit, or `null` if it has not been started (`404`).
 * Refetched on focus: the nurse and the doctor work on the same visit.
 */
export function useVisitConsultation(appointmentId: string | undefined) {
  return useQuery<Consultation | null>({
    enabled: !!appointmentId,
    queryKey: consultationKeys.visit(appointmentId ?? ""),
    queryFn: async () => {
      try {
        return await http.get<Consultation>(
          `/appointments/${appointmentId}/consultation`,
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    staleTime: 10_000,
  });
}

/** A patient's notes, newest first. */
export function usePatientConsultations(patientId: string, page = 1) {
  const params = { patient_id: patientId, page, page_size: 10 };
  return useQuery<Paginated<ConsultationSummary>>({
    enabled: !!patientId,
    queryKey: consultationKeys.list(params),
    queryFn: () =>
      http.getPaginated<ConsultationSummary>("/consultations", { params }),
    staleTime: 30_000,
  });
}

/**
 * Shared plumbing: every write answers with the whole note, which goes straight
 * into the visit cache. A 400/404/409 means the note changed under the screen
 * (someone finalized it, or started it in another tab), so it is refetched.
 */
function useVisitWrite<TInput>(
  appointmentId: string,
  call: (input: TInput) => Promise<Consultation>,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: (note) => {
      qc.setQueryData(consultationKeys.visit(appointmentId), note);
      return qc.invalidateQueries({
        queryKey: [...consultationKeys.all, "list"],
      });
    },
    onError: (err) => {
      if (
        err instanceof ApiError &&
        [400, 404, 409].includes(err.status ?? 0)
      ) {
        qc.invalidateQueries({
          queryKey: consultationKeys.visit(appointmentId),
        });
      }
    },
  });
}

/** Start the note (`POST /consultations`). Only the visit's doctor may. */
export function useStartConsultation(appointmentId: string) {
  return useVisitWrite<ConsultationSections>(appointmentId, (sections) =>
    http.post<Consultation>("/consultations", {
      appointment_id: appointmentId,
      ...sections,
    }),
  );
}

/** Save clinical sections of a draft (`PATCH /consultations/{id}`). */
export function useSaveConsultation(
  appointmentId: string,
  consultationId: string | undefined,
) {
  return useVisitWrite<ConsultationSections>(appointmentId, (sections) =>
    http.patch<Consultation>(`/consultations/${consultationId}`, sections),
  );
}

/** Record the visit's vitals, starting the draft if needed (`PUT /appointments/{id}/consultation/vitals`). */
export function useRecordVitals(appointmentId: string) {
  return useVisitWrite<Vitals>(appointmentId, (vitals) =>
    http.put<Consultation>(
      `/appointments/${appointmentId}/consultation/vitals`,
      { vitals },
    ),
  );
}

/** Lock the note (`POST /consultations/{id}/finalize`). */
export function useFinalizeConsultation(
  appointmentId: string,
  consultationId: string | undefined,
) {
  return useVisitWrite<void>(appointmentId, () =>
    http.post<Consultation>(`/consultations/${consultationId}/finalize`),
  );
}

/** Add to a finalized note (`POST /consultations/{id}/addenda`). */
export function useAddAddendum(
  appointmentId: string,
  consultationId: string | undefined,
) {
  return useVisitWrite<string>(appointmentId, (text) =>
    http.post<Consultation>(`/consultations/${consultationId}/addenda`, {
      text,
    }),
  );
}
