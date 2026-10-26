import Foundation

struct Photo: Decodable, Identifiable, Hashable {
    let id: String
    var caption: String
    var isActive: Bool
    let imageUrl: URL
}
struct Viewer: Decodable, Identifiable, Hashable {
    let id: String
    var name: String
    let viewerUrl: URL
    var photos: [Photo]
}
struct ViewersResponse: Decodable { let frames: [Viewer] }

enum PostcardError: LocalizedError {
    case server(String)
    var errorDescription: String? { if case .server(let message) = self { return message }; return nil }
}

struct PostcardAPI: Sendable {
    let server: URL
    let token: String
    static var decoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }
    func data(_ path: String, method: String = "GET", body: Data? = nil,
              contentType: String = "application/json") async throws -> Data {
        var request = URLRequest(url: server.appending(path: "api/v1/" + path))
        request.httpMethod = method
        request.httpBody = body
        request.timeoutInterval = 90
        request.setValue(contentType, forHTTPHeaderField: "Content-Type")
        if !token.isEmpty { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw PostcardError.server("Server did not respond.") }
        guard (200..<300).contains(response.statusCode) else {
            if response.statusCode == 401 { throw PostcardError.server("Session expired. Sign out, then sign in again.") }
            let message = (try? JSONSerialization.jsonObject(with: data) as? [String: String])?["detail"]
            throw PostcardError.server(message ?? "Request failed (\(response.statusCode)). Please try again.")
        }
        return data
    }
    func mutate(_ path: String, method: String = "POST", values: [String: Any] = [:]) async throws {
        _ = try await data(path, method: method, body: JSONSerialization.data(withJSONObject: values))
    }
    func upload(_ image: Data, viewerID: String, caption: String) async throws {
        let boundary = UUID().uuidString
        var body = Data()
        func append(_ text: String) { body.append(Data(text.utf8)) }
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n\(caption)\r\n")
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"image\"; filename=\"photo.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n")
        body.append(image)
        append("\r\n--\(boundary)--\r\n")
        _ = try await data("frames/\(viewerID)/photos/", method: "POST", body: body,
                           contentType: "multipart/form-data; boundary=\(boundary)")
    }
}
